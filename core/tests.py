from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import json
import os

from .models import SECFile, ExtractedTable, ProcessingTask


class SECFileModelTest(TestCase):
    """SECFile模型的测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com'
        )
        
        # 创建测试文件
        self.html_content = b'<html><body><table><tr><td>Test</td></tr></table></body></html>'
        self.test_file = SimpleUploadedFile(
            name='test_file.html',
            content=self.html_content,
            content_type='text/html'
        )
    
    def test_file_creation(self):
        """测试创建SEC文件记录"""
        sec_file = SECFile.objects.create(
            user=self.user,
            file=self.test_file,
            file_name='test_file.html',
            file_size=len(self.html_content),
            file_type='html',
            status='pending'
        )
        
        # 检查文件是否正确创建
        self.assertEqual(sec_file.file_name, 'test_file.html')
        self.assertEqual(sec_file.file_type, 'html')
        self.assertEqual(sec_file.status, 'pending')
        self.assertEqual(sec_file.user, self.user)
        
        # 检查文件是否实际保存在文件系统中
        self.assertTrue(os.path.exists(sec_file.file.path))
    
    def test_file_status_update(self):
        """测试更新SEC文件状态"""
        sec_file = SECFile.objects.create(
            user=self.user,
            file=self.test_file,
            file_name='test_file.html',
            file_size=len(self.html_content),
            file_type='html',
            status='pending'
        )
        
        # 更新文件状态为处理中
        sec_file.status = 'processing'
        sec_file.processing_started_at = timezone.now()
        sec_file.save()
        
        # 从数据库重新获取文件
        updated_file = SECFile.objects.get(id=sec_file.id)
        
        # 检查状态是否正确更新
        self.assertEqual(updated_file.status, 'processing')
        self.assertIsNotNone(updated_file.processing_started_at)
        
        # 完成处理
        updated_file.status = 'completed'
        updated_file.processing_completed_at = timezone.now()
        updated_file.processing_time = 1.23  # 秒
        updated_file.save()
        
        # 再次从数据库获取文件
        completed_file = SECFile.objects.get(id=sec_file.id)
        
        # 检查状态是否正确更新
        self.assertEqual(completed_file.status, 'completed')
        self.assertIsNotNone(completed_file.processing_completed_at)
        self.assertEqual(completed_file.processing_time, 1.23)
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试过程中创建的媒体文件
        for sec_file in SECFile.objects.all():
            if os.path.exists(sec_file.file.path):
                os.remove(sec_file.file.path)


class ExtractedTableModelTest(TestCase):
    """ExtractedTable模型的测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        
        # 创建测试文件
        self.test_file = SimpleUploadedFile(
            name='test_file.html',
            content=b'<html><body><table><tr><td>Test</td></tr></table></body></html>',
            content_type='text/html'
        )
        
        # 创建SEC文件记录
        self.sec_file = SECFile.objects.create(
            user=self.user,
            file=self.test_file,
            file_name='test_file.html',
            file_size=len(self.test_file.read()),
            file_type='html',
            status='completed'
        )
        
        # 准备表格数据
        self.table_data = {
            'headers': ['项目', '2023-12-31', '2022-12-31'],
            'rows': [
                ['资产总计', 1000000, 900000],
                ['负债总计', 600000, 500000],
                ['股东权益', 400000, 400000]
            ]
        }
    
    def test_table_creation(self):
        """测试创建提取表格记录"""
        table = ExtractedTable.objects.create(
            file=self.sec_file,
            table_type='balance_sheet',
            table_name='资产负债表',
            table_index=1,
            table_data=self.table_data,
            confidence_score=0.95
        )
        
        # 检查表格是否正确创建
        self.assertEqual(table.table_type, 'balance_sheet')
        self.assertEqual(table.table_name, '资产负债表')
        self.assertEqual(table.table_index, 1)
        self.assertEqual(table.confidence_score, 0.95)
        
        # 检查JSON数据是否正确存储
        self.assertEqual(table.table_data['headers'], self.table_data['headers'])
        self.assertEqual(table.table_data['rows'], self.table_data['rows'])
        
        # 检查表格是否关联到正确的SEC文件
        self.assertEqual(table.file, self.sec_file)
    
    def test_table_display_name(self):
        """测试表格显示名称"""
        table = ExtractedTable.objects.create(
            file=self.sec_file,
            table_type='balance_sheet',
            table_name='资产负债表',
            table_index=1,
            table_data=self.table_data,
            confidence_score=0.95
        )
        
        # 测试__str__方法
        self.assertEqual(str(table), '资产负债表 - 资产负债表')
        
        # 测试get_table_type_display方法
        self.assertEqual(table.get_table_type_display(), '资产负债表')
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试过程中创建的媒体文件
        for sec_file in SECFile.objects.all():
            if os.path.exists(sec_file.file.path):
                os.remove(sec_file.file.path)


class ProcessingTaskModelTest(TestCase):
    """ProcessingTask模型的测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        
        # 创建测试文件
        self.test_file = SimpleUploadedFile(
            name='test_file.html',
            content=b'<html><body><table><tr><td>Test</td></tr></table></body></html>',
            content_type='text/html'
        )
        
        # 创建SEC文件记录
        self.sec_file = SECFile.objects.create(
            user=self.user,
            file=self.test_file,
            file_name='test_file.html',
            file_size=len(self.test_file.read()),
            file_type='html',
            status='pending'
        )
    
    def test_task_creation(self):
        """测试创建处理任务记录"""
        task = ProcessingTask.objects.create(
            file=self.sec_file,
            celery_task_id='test-task-id-123',
            status='queued'
        )
        
        # 检查任务是否正确创建
        self.assertEqual(task.celery_task_id, 'test-task-id-123')
        self.assertEqual(task.status, 'queued')
        self.assertIsNotNone(task.task_id)  # UUID应该自动生成
        
        # 检查任务是否关联到正确的SEC文件
        self.assertEqual(task.file, self.sec_file)
    
    def test_task_status_update(self):
        """测试更新任务状态"""
        task = ProcessingTask.objects.create(
            file=self.sec_file,
            celery_task_id='test-task-id-123',
            status='queued'
        )
        
        # 更新任务状态为运行中
        task.status = 'running'
        task.save()
        
        # 从数据库重新获取任务
        updated_task = ProcessingTask.objects.get(id=task.id)
        
        # 检查状态是否正确更新
        self.assertEqual(updated_task.status, 'running')
        
        # 完成任务
        result_data = {
            'tables_count': 3,
            'processing_time': 2.45
        }
        
        updated_task.status = 'completed'
        updated_task.result = result_data
        updated_task.save()
        
        # 再次从数据库获取任务
        completed_task = ProcessingTask.objects.get(id=task.id)
        
        # 检查状态和结果是否正确更新
        self.assertEqual(completed_task.status, 'completed')
        self.assertEqual(completed_task.result, result_data)
    
    def test_task_error_handling(self):
        """测试任务错误处理"""
        task = ProcessingTask.objects.create(
            file=self.sec_file,
            celery_task_id='test-task-id-123',
            status='running'
        )
        
        # 模拟任务失败
        error_message = "测试错误：文件处理失败"
        task.status = 'failed'
        task.error_message = error_message
        task.save()
        
        # 从数据库重新获取任务
        failed_task = ProcessingTask.objects.get(id=task.id)
        
        # 检查错误信息是否正确更新
        self.assertEqual(failed_task.status, 'failed')
        self.assertEqual(failed_task.error_message, error_message)
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试过程中创建的媒体文件
        for sec_file in SECFile.objects.all():
            if os.path.exists(sec_file.file.path):
                os.remove(sec_file.file.path)
