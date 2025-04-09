from django.shortcuts import render
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from core.models import SECFile, ExtractedTable, ProcessingTask
from .serializers import SECFileSerializer, ExtractedTableSerializer, ProcessingTaskSerializer
from extraction.tasks import process_sec_file


class SECFileViewSet(viewsets.ModelViewSet):
    """SEC文件视图集"""
    serializer_class = SECFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'file_type', 'company_name', 'filing_type']
    search_fields = ['file_name', 'company_name', 'company_cik']
    ordering_fields = ['created_at', 'updated_at', 'file_name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """获取当前用户的SEC文件"""
        return SECFile.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """创建SEC文件并启动处理任务"""
        sec_file = serializer.save()
        
        # 启动异步处理任务
        task = process_sec_file.delay(sec_file.id)
        
        # 创建处理任务记录
        ProcessingTask.objects.create(
            file=sec_file,
            celery_task_id=task.id,
            status='queued'
        )
    
    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """重新处理文件"""
        sec_file = self.get_object()
        
        # 更新文件状态
        sec_file.status = 'pending'
        sec_file.processing_error = None
        sec_file.save()
        
        # 启动异步处理任务
        task = process_sec_file.delay(sec_file.id)
        
        # 创建处理任务记录
        ProcessingTask.objects.create(
            file=sec_file,
            celery_task_id=task.id,
            status='queued'
        )
        
        return Response({'status': 'processing'})


class ExtractedTableViewSet(viewsets.ReadOnlyModelViewSet):
    """提取表格视图集"""
    serializer_class = ExtractedTableSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['table_type', 'file']
    search_fields = ['table_name']
    ordering_fields = ['table_index', 'created_at']
    ordering = ['table_index']
    
    def get_queryset(self):
        """获取当前用户的提取表格"""
        return ExtractedTable.objects.filter(file__user=self.request.user)
    
    @action(detail=False)
    def by_file(self, request):
        """按文件获取表格"""
        file_id = request.query_params.get('file_id')
        if not file_id:
            return Response({'error': '需要file_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 确保文件属于当前用户
        get_object_or_404(SECFile, id=file_id, user=request.user)
        
        # 获取文件的表格
        tables = ExtractedTable.objects.filter(file_id=file_id)
        serializer = self.get_serializer(tables, many=True)
        
        return Response(serializer.data)


class ProcessingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """处理任务视图集"""
    serializer_class = ProcessingTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'file']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """获取当前用户的处理任务"""
        return ProcessingTask.objects.filter(file__user=self.request.user)
