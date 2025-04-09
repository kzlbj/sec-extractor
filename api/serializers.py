from rest_framework import serializers
from core.models import SECFile, ExtractedTable, ProcessingTask
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class ExtractedTableSerializer(serializers.ModelSerializer):
    """提取表格序列化器"""
    
    table_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ExtractedTable
        fields = [
            'id', 'file', 'table_type', 'table_type_display', 'table_name', 
            'table_index', 'table_data', 'confidence_score', 
            'created_at', 'updated_at'
        ]
    
    def get_table_type_display(self, obj):
        """获取表格类型显示名称"""
        return obj.get_table_type_display()


class SECFileSerializer(serializers.ModelSerializer):
    """SEC文件序列化器"""
    
    user = UserSerializer(read_only=True)
    extracted_tables = ExtractedTableSerializer(many=True, read_only=True)
    file_type_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = SECFile
        fields = [
            'id', 'user', 'file', 'file_name', 'file_size', 
            'file_type', 'file_type_display', 'status', 'status_display',
            'company_name', 'company_cik', 'filing_date', 'filing_type',
            'processing_started_at', 'processing_completed_at', 
            'processing_time', 'processing_error',
            'created_at', 'updated_at', 'extracted_tables'
        ]
        read_only_fields = [
            'id', 'user', 'file_name', 'file_size', 'file_type', 
            'status', 'company_name', 'company_cik', 'filing_date', 
            'filing_type', 'processing_started_at', 'processing_completed_at', 
            'processing_time', 'processing_error', 'created_at', 'updated_at'
        ]
    
    def get_file_type_display(self, obj):
        """获取文件类型显示名称"""
        return obj.get_file_type_display()
    
    def get_status_display(self, obj):
        """获取状态显示名称"""
        return obj.get_status_display()
    
    def create(self, validated_data):
        """创建SEC文件记录"""
        # 获取当前用户
        user = self.context['request'].user
        
        # 获取上传的文件
        file = validated_data['file']
        
        # 确定文件类型
        file_name = file.name
        file_ext = file_name.lower().split('.')[-1]
        
        if file_ext == 'xbrl' or file_ext == 'xml':
            file_type = 'xbrl'
        elif file_ext == 'html' or file_ext == 'htm':
            file_type = 'html'
        else:
            file_type = 'unknown'
        
        # 创建SEC文件记录
        sec_file = SECFile.objects.create(
            user=user,
            file=file,
            file_name=file_name,
            file_size=file.size,
            file_type=file_type,
            status='pending'
        )
        
        return sec_file


class ProcessingTaskSerializer(serializers.ModelSerializer):
    """处理任务序列化器"""
    
    file = SECFileSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcessingTask
        fields = [
            'id', 'task_id', 'file', 'celery_task_id', 
            'status', 'status_display', 'result', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'task_id', 'file', 'celery_task_id', 
            'status', 'result', 'error_message',
            'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        """获取状态显示名称"""
        return obj.get_status_display()