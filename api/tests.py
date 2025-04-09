from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
import json
import os

from core.models import SECFile, ExtractedTable, ProcessingTask


class APIAuthTestCase(APITestCase):
    """API认证测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com'
        )
        
        # 创建API客户端
        self.client = APIClient()
    
    def test_auth_required(self):
        """测试API端点需要认证"""
        # 未认证的请求
        response = self.client.get('/api/files/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # 认证的请求
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/files/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SECFileAPITestCase(APITestCase):
    """SEC文件API测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            email='test@example.com'
        )
        
        # 创建额外的测试用户
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='otherpassword',
            email='other@example.com'
        )
        
        # 认证API客户端
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # 准备测试文件
        self.html_content = b'<html><body><table><tr><td>Test</td></tr></table></body></html>'
        self.test_file = SimpleUploadedFile(
            name='test_file.html',
            content=self.html_content,
            content_type='text/html'
        )
        
        # 创建测试SEC文件
        self.sec_file = SECFile.objects.create(
            user=self.user,
            file=self.test_file,
            file_name='test_file.html',
            file_size=len(self.html_content),
            file_type='html',
            status='completed'
        )
        
        # 为其他用户创建文件
        self.other_file = SECFile.objects.create(
            user=self.other_user,
            file=self.test_file,
            file_name='other_file.html',
            file_size=len(self.html_content),
            file_type='html',
            status='completed'
        )
    
    def test_list_files(self):
        """测试获取SEC文件列表"""
        response = self.client.get('/api/files/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 验证只能看到自己的文件
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['file_name'], 'test_file.html')
    
    def test_file_detail(self):
        """测试获取SEC文件详情"""
        response = self.client.get(f'/api/files/{self.sec_file.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['file_name'], 'test_file.html')
        
        # 尝试访问其他用户的文件
        response = self.client.get(f'/api/files/{self.other_file.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_file_upload(self):
        """测试上传SEC文件"""
        # 准备上传数据
        upload_file = SimpleUploadedFile(
            name='upload_test.html',
            content=b'<html><body><h1>Upload Test</h1></body></html>',
            content_type='text/html'
        )
        
        response = self.client.post('/api/files/', {'file': upload_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['file_name'], 'upload_test.html')
        self.assertEqual(response.data['file_type'], 'html')
        
        # 验证文件已添加到数据库
        self.assertTrue(SECFile.objects.filter(file_name='upload_test.html').exists())
    
    def test_file_reprocess(self):
        """测试重新处理文件"""
        # 更新文件状态为已完成
        self.sec_file.status = 'completed'
        self.sec_file.save()
        
        # 重新处理文件
        response = self.client.post(f'/api/files/{self.sec_file.id}/reprocess/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'processing')
        
        # 验证文件状态已更新
        updated_file = SECFile.objects.get(id=self.sec_file.id)
        self.assertEqual(updated_file.status, 'pending')
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试过程中创建的媒体文件
        for sec_file in SECFile.objects.all():
            if os.path.exists(sec_file.file.path):
                try:
                    os.remove(sec_file.file.path)
                except (FileNotFoundError, PermissionError):
                    pass


class ExtractedTableAPITestCase(APITestCase):
    """提取表格API测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        
        # 认证API客户端
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
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
        
        # 创建表格数据
        self.table_data = {
            'headers': ['项目', '2023-12-31', '2022-12-31'],
            'rows': [
                ['资产总计', 1000000, 900000],
                ['负债总计', 600000, 500000],
                ['股东权益', 400000, 400000]
            ]
        }
        
        # 创建提取表格记录
        self.table = ExtractedTable.objects.create(
            file=self.sec_file,
            table_type='balance_sheet',
            table_name='资产负债表',
            table_index=1,
            table_data=self.table_data,
            confidence_score=0.95
        )
        
        # 创建额外的表格
        self.income_table = ExtractedTable.objects.create(
            file=self.sec_file,
            table_type='income_statement',
            table_name='利润表',
            table_index=2,
            table_data=self.table_data,
            confidence_score=0.90
        )
    
    def test_list_tables(self):
        """测试获取提取表格列表"""
        response = self.client.get('/api/tables/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 验证可以看到所有表格
        self.assertEqual(len(response.data['results']), 2)
    
    def test_table_detail(self):
        """测试获取提取表格详情"""
        response = self.client.get(f'/api/tables/{self.table.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['table_name'], '资产负债表')
        self.assertEqual(response.data['table_type'], 'balance_sheet')
        
        # 检查表格数据
        self.assertEqual(response.data['table_data'], self.table_data)
    
    def test_filter_tables_by_type(self):
        """测试按类型筛选表格"""
        response = self.client.get('/api/tables/?table_type=balance_sheet')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 验证只返回资产负债表
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['table_type'], 'balance_sheet')
    
    def test_filter_tables_by_file(self):
        """测试按文件筛选表格"""
        response = self.client.get(f'/api/tables/?file={self.sec_file.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 验证返回文件的所有表格
        self.assertEqual(len(response.data['results']), 2)
    
    def test_tables_by_file_endpoint(self):
        """测试通过特定端点获取文件的表格"""
        response = self.client.get(f'/api/tables/by_file/?file_id={self.sec_file.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 验证返回了文件的所有表格
        self.assertEqual(len(response.data), 2)
        
        # 验证返回了正确的表格类型
        table_types = [table['table_type'] for table in response.data]
        self.assertIn('balance_sheet', table_types)
        self.assertIn('income_statement', table_types)
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试过程中创建的媒体文件
        for sec_file in SECFile.objects.all():
            if os.path.exists(sec_file.file.path):
                try:
                    os.remove(sec_file.file.path)
                except (FileNotFoundError, PermissionError):
                    pass
