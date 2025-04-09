from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import SECFile, ExtractedTable, ProcessingTask


@admin.register(SECFile)
class SECFileAdmin(admin.ModelAdmin):
    """SEC文件管理界面"""
    list_display = ('file_name', 'file_type', 'status', 'user', 'company_name', 
                    'tables_count', 'processing_time_display', 'created_at')
    list_filter = ('file_type', 'status', 'created_at')
    search_fields = ('file_name', 'company_name', 'company_cik', 'user__username')
    readonly_fields = ('processing_time', 'processing_started_at', 'processing_completed_at', 
                      'file_size', 'created_at', 'updated_at')
    fieldsets = (
        ('基本信息', {
            'fields': ('file', 'file_name', 'file_type', 'file_size', 'status', 'user')
        }),
        ('公司信息', {
            'fields': ('company_name', 'company_cik', 'filing_date', 'filing_type')
        }),
        ('处理信息', {
            'fields': ('processing_started_at', 'processing_completed_at', 'processing_time', 'processing_error')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def tables_count(self, obj):
        """显示提取的表格数量"""
        count = obj.extracted_tables.count()
        if count > 0:
            url = reverse('admin:core_extractedtable_changelist') + f'?file__id__exact={obj.id}'
            return format_html('<a href="{}">{} 个表格</a>', url, count)
        return '无表格'
    tables_count.short_description = '表格数量'
    
    def processing_time_display(self, obj):
        """格式化处理时间显示"""
        if obj.processing_time is not None:
            return f'{obj.processing_time:.2f} 秒'
        return '-'
    processing_time_display.short_description = '处理时间'


@admin.register(ExtractedTable)
class ExtractedTableAdmin(admin.ModelAdmin):
    """提取表格管理界面"""
    list_display = ('table_name', 'table_type_display', 'file_link', 'confidence_score_display', 'created_at')
    list_filter = ('table_type', 'created_at')
    search_fields = ('table_name', 'file__file_name', 'file__company_name')
    readonly_fields = ('created_at', 'updated_at', 'confidence_score', 'table_index', 'preview_data')
    fieldsets = (
        ('基本信息', {
            'fields': ('file', 'table_name', 'table_type', 'table_index', 'confidence_score')
        }),
        ('表格数据', {
            'fields': ('preview_data', 'table_data')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def table_type_display(self, obj):
        """显示表格类型名称"""
        return obj.get_table_type_display()
    table_type_display.short_description = '表格类型'
    
    def file_link(self, obj):
        """链接到文件详情页"""
        link = reverse('admin:core_secfile_change', args=[obj.file.id])
        return format_html('<a href="{}">{}</a>', link, obj.file.file_name)
    file_link.short_description = '文件'
    
    def confidence_score_display(self, obj):
        """信心分数显示"""
        if obj.confidence_score is not None:
            return f'{obj.confidence_score * 100:.1f}%'
        return '-'
    confidence_score_display.short_description = '置信度'
    
    def preview_data(self, obj):
        """预览表格数据"""
        html = '<div style="max-width:800px; overflow-x:auto;"><table border="1" cellpadding="5" cellspacing="0">'
        
        # 添加表头
        if 'headers' in obj.table_data:
            html += '<tr>'
            for header in obj.table_data['headers']:
                html += f'<th>{header}</th>'
            html += '</tr>'
        
        # 添加行数据（最多显示10行）
        if 'rows' in obj.table_data:
            for i, row in enumerate(obj.table_data['rows'][:10]):
                html += '<tr>'
                for cell in row:
                    html += f'<td>{cell}</td>'
                html += '</tr>'
            
            # 如果有更多行
            if len(obj.table_data['rows']) > 10:
                html += f'<tr><td colspan="{len(obj.table_data["headers"])}" style="text-align:center;">... 还有 {len(obj.table_data["rows"]) - 10} 行 ...</td></tr>'
        
        html += '</table></div>'
        return format_html(html)
    preview_data.short_description = '数据预览'


@admin.register(ProcessingTask)
class ProcessingTaskAdmin(admin.ModelAdmin):
    """处理任务管理界面"""
    list_display = ('task_id', 'file_link', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    readonly_fields = ('task_id', 'celery_task_id', 'created_at', 'updated_at', 'formatted_result')
    fieldsets = (
        ('基本信息', {
            'fields': ('task_id', 'file', 'celery_task_id', 'status')
        }),
        ('结果信息', {
            'fields': ('formatted_result', 'error_message')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def file_link(self, obj):
        """链接到文件详情页"""
        link = reverse('admin:core_secfile_change', args=[obj.file.id])
        return format_html('<a href="{}">{}</a>', link, obj.file.file_name)
    file_link.short_description = '文件'
    
    def formatted_result(self, obj):
        """格式化显示任务结果"""
        if not obj.result:
            return '-'
        
        html = '<div style="max-width:600px; overflow-x:auto;"><dl>'
        for key, value in obj.result.items():
            html += f'<dt style="font-weight:bold;">{key}</dt><dd>{value}</dd>'
        html += '</dl></div>'
        
        return format_html(html)
    formatted_result.short_description = '处理结果'
