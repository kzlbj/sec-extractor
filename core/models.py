from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def file_upload_path(instance, filename):
    """为上传的文件生成唯一路径"""
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join('uploads', unique_filename)


class SECFile(models.Model):
    """SEC文件模型，存储上传的XBRL或HTML文件"""
    FILE_TYPE_CHOICES = (
        ('xbrl', 'XBRL文件'),
        ('html', 'HTML文件'),
        ('unknown', '未知类型'),
    )
    
    FILE_STATUS_CHOICES = (
        ('pending', '等待处理'),
        ('processing', '处理中'),
        ('completed', '处理完成'),
        ('failed', '处理失败'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sec_files')
    file = models.FileField(upload_to=file_upload_path)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # 文件大小（字节）
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='unknown')
    status = models.CharField(max_length=20, choices=FILE_STATUS_CHOICES, default='pending')
    
    # 元数据
    company_name = models.CharField(max_length=255, blank=True, null=True)
    company_cik = models.CharField(max_length=20, blank=True, null=True)  # SEC CIK号码
    filing_date = models.DateField(blank=True, null=True)
    filing_type = models.CharField(max_length=20, blank=True, null=True)  # 10-K, 10-Q等
    
    # 处理信息
    processing_started_at = models.DateTimeField(blank=True, null=True)
    processing_completed_at = models.DateTimeField(blank=True, null=True)
    processing_time = models.FloatField(blank=True, null=True)  # 处理时间（秒）
    processing_error = models.TextField(blank=True, null=True)
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.file_name} ({self.file_type})"


class ExtractedTable(models.Model):
    """从SEC文件中提取的表格"""
    TABLE_TYPE_CHOICES = (
        ('balance_sheet', '资产负债表'),
        ('income_statement', '利润表'),
        ('cash_flow', '现金流量表'),
        ('unknown', '未知类型'),
        ('other', '其他类型'),
    )
    
    file = models.ForeignKey(SECFile, on_delete=models.CASCADE, related_name='extracted_tables')
    table_type = models.CharField(max_length=20, choices=TABLE_TYPE_CHOICES, default='unknown')
    table_name = models.CharField(max_length=255, blank=True, null=True)
    table_index = models.PositiveIntegerField()  # 表格在文档中的索引
    table_data = models.JSONField()  # 存储表格数据的JSON
    confidence_score = models.FloatField(default=0.0)  # ML模型的置信度得分
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_table_type_display()} - {self.table_name or f'表格 #{self.table_index}'}"
    
    class Meta:
        ordering = ['table_index']


class ProcessingTask(models.Model):
    """处理任务模型，跟踪文件处理任务"""
    TASK_STATUS_CHOICES = (
        ('queued', '排队中'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    )
    
    task_id = models.UUIDField(default=uuid.uuid4, editable=False)
    file = models.ForeignKey(SECFile, on_delete=models.CASCADE, related_name='tasks')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='queued')
    result = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"任务 {self.task_id} - {self.get_status_display()}"
