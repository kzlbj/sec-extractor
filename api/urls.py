from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from .views import SECFileViewSet, ExtractedTableViewSet, ProcessingTaskViewSet

# 创建API路由
router = DefaultRouter()
router.register(r'files', SECFileViewSet, basename='secfile')
router.register(r'tables', ExtractedTableViewSet, basename='extractedtable')
router.register(r'tasks', ProcessingTaskViewSet, basename='processingtask')

# 创建API文档视图
schema_view = get_schema_view(
    openapi.Info(
        title="SEC财务文件表格提取API",
        default_version='v1',
        description="SEC财务文件表格提取系统的API接口文档",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@secextractor.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.IsAuthenticated,),
)

urlpatterns = [
    # API路由
    path('', include(router.urls)),
    
    # 认证路由
    path('auth/', include('rest_framework.urls')),
    
    # API文档
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API JSON文档
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
] 