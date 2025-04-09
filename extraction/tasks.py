import time
import logging
import traceback
from celery import shared_task, chord, group
from datetime import datetime
from django.utils import timezone
from django.db.models import Count
from django.db import transaction
from celery.exceptions import MaxRetriesExceededError
from core.models import SECFile, ProcessingTask

from .processors.xbrl_processor import XBRLProcessor
from .processors.html_processor import HTMLProcessor
from .classifiers.table_classifier import TableClassifier

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_sec_file(self, file_id):
    """处理SEC文件的Celery任务"""
    start_time = time.time()
    sec_file = None
    task = None
    
    logger.info(f"开始处理文件: ID={file_id}")
    
    try:
        # 获取文件和任务记录
        sec_file = SECFile.objects.select_for_update().get(id=file_id)
        
        # 使用事务确保任务状态的一致性
        with transaction.atomic():
            task, created = ProcessingTask.objects.get_or_create(
                file=sec_file,
                defaults={
                    'celery_task_id': self.request.id, 
                    'status': 'running'
                }
            )
            
            if not created:
                # 任务已存在，检查是否已完成
                if task.status == 'completed':
                    logger.info(f"文件ID={file_id}已经处理完成，跳过处理")
                    return {
                        'status': 'skipped',
                        'file_id': file_id,
                        'message': '文件已处理'
                    }
                
                # 更新任务状态
                task.celery_task_id = self.request.id
                task.status = 'running'
                task.save(update_fields=['celery_task_id', 'status', 'updated_at'])
            
            # 更新文件状态
            if sec_file.status != 'processing':
                sec_file.status = 'processing'
                sec_file.processing_started_at = timezone.now()
                sec_file.processing_error = None  # 清除之前的错误信息
                sec_file.save(update_fields=['status', 'processing_started_at', 'processing_error', 'updated_at'])
        
        # 记录文件元数据
        logger.info(f"处理文件: {sec_file.file_name} (类型: {sec_file.file_type}, 大小: {sec_file.file_size} 字节)")
        
        # 验证文件类型
        if sec_file.file_type not in ['xbrl', 'html']:
            # 尝试推断文件类型
            file_ext = sec_file.file_name.lower().split('.')[-1]
            if file_ext in ['xml', 'xbrl']:
                sec_file.file_type = 'xbrl'
                sec_file.save(update_fields=['file_type'])
                logger.info(f"已根据扩展名更新文件类型为: xbrl")
            elif file_ext in ['html', 'htm']:
                sec_file.file_type = 'html'
                sec_file.save(update_fields=['file_type'])
                logger.info(f"已根据扩展名更新文件类型为: html")
            else:
                raise ValueError(f"不支持的文件类型: {sec_file.file_type}")
        
        # 根据文件类型选择处理器
        if sec_file.file_type == 'xbrl':
            processor = XBRLProcessor()
        elif sec_file.file_type == 'html':
            processor = HTMLProcessor()
        else:
            raise ValueError(f"不支持的文件类型: {sec_file.file_type}")
        
        # 处理文件
        logger.info(f"开始使用{sec_file.file_type}处理器处理文件")
        tables = processor.process(sec_file.file.path)
        
        # 使用分类器识别表格类型
        logger.info(f"对提取的 {len(tables)} 个表格进行分类")
        classifier = TableClassifier()
        classified_tables = classifier.classify(tables)
        
        # 将表格保存到数据库
        logger.info(f"将 {len(classified_tables)} 个分类后的表格保存到数据库")
        
        # 使用事务进行批量插入，提高性能
        with transaction.atomic():
            # 先删除已有的表格
            sec_file.extracted_tables.all().delete()
            
            # 批量创建表格记录
            for idx, table in enumerate(classified_tables):
                try:
                    sec_file.extracted_tables.create(
                        table_type=table['table_type'],
                        table_name=table.get('table_name', '未命名表格'),
                        table_index=idx,
                        table_data=table['table_data'],
                        confidence_score=table.get('confidence_score', 0.0)
                    )
                except Exception as e:
                    logger.error(f"保存表格 #{idx} 时出错: {str(e)}")
        
        # 计算处理时间
        processing_time = time.time() - start_time
        
        # 使用事务更新文件和任务状态
        with transaction.atomic():
            # 更新文件状态
            sec_file.status = 'completed'
            sec_file.processing_completed_at = timezone.now()
            sec_file.processing_time = processing_time
            sec_file.save(update_fields=['status', 'processing_completed_at', 'processing_time', 'updated_at'])
            
            # 统计各类型表格数量
            table_types_count = {}
            for table_type, count in sec_file.extracted_tables.values('table_type').annotate(count=Count('id')):
                table_types_count[table_type] = count
            
            # 更新任务状态
            task.status = 'completed'
            task.result = {
                'tables_count': len(classified_tables),
                'processing_time': processing_time,
                'table_types': table_types_count
            }
            task.save(update_fields=['status', 'result', 'updated_at'])
        
        logger.info(f"文件处理成功完成，耗时: {processing_time:.2f}秒，提取表格: {len(classified_tables)} 个")
        
        return {
            'status': 'success',
            'file_id': file_id,
            'tables_count': len(classified_tables),
            'processing_time': processing_time,
            'table_types': table_types_count
        }
    
    except Exception as e:
        error_details = traceback.format_exc()
        processing_time = time.time() - start_time
        logger.exception(f"处理文件 ID={file_id} 时出错 (耗时: {processing_time:.2f}秒): {str(e)}\n{error_details}")
        
        # 更新文件和任务状态
        try:
            if sec_file:
                sec_file.status = 'failed'
                sec_file.processing_error = f"{str(e)}\n{error_details[:500]}"  # 截断以避免过长
                sec_file.save(update_fields=['status', 'processing_error', 'updated_at'])
            
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                task.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception as nested_e:
            logger.error(f"更新状态时出错: {str(nested_e)}")
        
        # 重试机制优化
        try:
            countdown = min(60 * 5 * (self.request.retries + 1), 60 * 60)  # 5分钟到1小时不等的递增重试间隔
            logger.warning(f"计划在 {countdown} 秒后重试 (尝试次数: {self.request.retries + 1})")
            self.retry(exc=e, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(f"超过最大重试次数，放弃处理文件 ID={file_id}")
        
        return {
            'status': 'error',
            'file_id': file_id,
            'error': str(e),
            'processing_time': processing_time
        }


@shared_task
def process_files_batch(file_ids):
    """
    批量处理多个SEC文件
    
    参数:
        file_ids (list): SEC文件ID列表
        
    返回:
        dict: 处理结果统计
    """
    logger.info(f"开始批量处理 {len(file_ids)} 个文件")
    
    # 创建任务组
    jobs = group(process_sec_file.s(file_id) for file_id in file_ids)
    
    # 创建回调任务
    callback = summarize_batch_results.s()
    
    # 执行任务组和回调
    result = chord(jobs)(callback)
    
    return {
        'status': 'started',
        'batch_size': len(file_ids),
        'task_id': result.id
    }


@shared_task
def summarize_batch_results(results):
    """
    汇总批量处理的结果
    
    参数:
        results (list): 每个文件处理的结果
        
    返回:
        dict: 汇总结果
    """
    success_count = sum(1 for r in results if r.get('status') == 'success')
    error_count = sum(1 for r in results if r.get('status') == 'error')
    skipped_count = sum(1 for r in results if r.get('status') == 'skipped')
    
    total_tables = sum(r.get('tables_count', 0) for r in results if 'tables_count' in r)
    total_time = sum(r.get('processing_time', 0) for r in results if 'processing_time' in r)
    avg_time = total_time / len(results) if results else 0
    
    logger.info(f"批量处理完成: 总共 {len(results)} 个文件, "
                f"成功 {success_count}, 失败 {error_count}, 跳过 {skipped_count}, "
                f"提取 {total_tables} 个表格, 平均处理时间 {avg_time:.2f}秒")
    
    return {
        'total': len(results),
        'success': success_count,
        'error': error_count,
        'skipped': skipped_count,
        'total_tables': total_tables,
        'total_processing_time': total_time,
        'avg_processing_time': avg_time
    }