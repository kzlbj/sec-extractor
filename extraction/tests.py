from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import os
import json
from unittest.mock import patch, MagicMock

from core.models import SECFile, ExtractedTable
from .processors.xbrl_processor import XBRLProcessor
from .processors.html_processor import HTMLProcessor
from .classifiers.table_classifier import TableClassifier
from .tasks import process_sec_file


class XBRLProcessorTest(TestCase):
    """XBRL处理器测试"""
    
    @patch('extraction.processors.xbrl_processor.ModelManager')
    @patch('extraction.processors.xbrl_processor.ModelXbrl')
    @patch('extraction.processors.xbrl_processor.Cntlr')
    def test_process_method_error_handling(self, mock_cntlr, mock_model_xbrl, mock_model_manager):
        """测试XBRL处理器错误处理"""
        # 设置模拟对象行为
        mock_controller = MagicMock()
        mock_cntlr.return_value = mock_controller
        
        mock_manager = MagicMock()
        mock_model_manager.initialize.return_value = mock_manager
        
        # 创建处理器实例
        processor = XBRLProcessor()
        
        # 模拟文件不存在的情况
        with self.assertRaises(FileNotFoundError):
            processor.process('non_existent_file.xbrl')
        
        # 模拟加载文件失败的情况
        mock_model_xbrl.load.return_value = None
        with self.assertRaises(ValueError):
            processor.process('test_file.xbrl')


class HTMLProcessorTest(TestCase):
    """HTML处理器测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试目录
        os.makedirs('test_files', exist_ok=True)
        
        # 创建简单的HTML文件用于测试
        self.html_content = """
        <html>
        <body>
            <h1>测试报表</h1>
            <table>
                <tr>
                    <th>资产</th>
                    <th>2023-12-31</th>
                    <th>2022-12-31</th>
                </tr>
                <tr>
                    <td>资产总计</td>
                    <td>1000000</td>
                    <td>900000</td>
                </tr>
                <tr>
                    <td>负债总计</td>
                    <td>600000</td>
                    <td>500000</td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        # 保存测试文件
        self.test_file_path = 'test_files/test_table.html'
        with open(self.test_file_path, 'w', encoding='utf-8') as f:
            f.write(self.html_content)
    
    def test_html_processing(self):
        """测试HTML处理功能"""
        processor = HTMLProcessor()
        tables = processor.process(self.test_file_path)
        
        # 验证是否提取了表格
        self.assertGreater(len(tables), 0)
        
        # 验证表格内容
        table = tables[0]
        self.assertIn('table_data', table)
        self.assertIn('headers', table['table_data'])
        self.assertIn('rows', table['table_data'])
    
    def test_table_extraction(self):
        """测试表格提取功能"""
        processor = HTMLProcessor()
        
        # 使用BeautifulSoup解析HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.html_content, 'html.parser')
        
        # 提取表格
        tables = processor._extract_tables(soup)
        
        # 验证是否提取了表格
        self.assertGreater(len(tables), 0)
        
        # 验证表格结构
        table = tables[0]
        self.assertIn('table_name', table)
        self.assertIn('table_index', table)
        self.assertIn('table_data', table)
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试文件
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
        
        # 删除测试目录
        if os.path.exists('test_files'):
            os.rmdir('test_files')


class TableClassifierTest(TestCase):
    """表格分类器测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 准备测试表格数据
        self.balance_sheet_data = {
            'table_name': '资产负债表',
            'table_index': 0,
            'table_data': {
                'headers': ['项目', '2023-12-31', '2022-12-31'],
                'rows': [
                    ['资产', None, None],
                    ['流动资产', None, None],
                    ['货币资金', 100000, 80000],
                    ['资产总计', 1000000, 900000],
                    ['负债和股东权益', None, None],
                    ['负债总计', 600000, 500000],
                    ['股东权益', 400000, 400000]
                ]
            }
        }
        
        self.income_statement_data = {
            'table_name': '利润表',
            'table_index': 1,
            'table_data': {
                'headers': ['项目', '2023年', '2022年'],
                'rows': [
                    ['营业收入', 500000, 450000],
                    ['营业成本', 300000, 250000],
                    ['毛利润', 200000, 200000],
                    ['营业费用', 100000, 100000],
                    ['净利润', 100000, 100000]
                ]
            }
        }
        
        self.cash_flow_data = {
            'table_name': '现金流量表',
            'table_index': 2,
            'table_data': {
                'headers': ['项目', '2023年', '2022年'],
                'rows': [
                    ['经营活动产生的现金流量', None, None],
                    ['经营活动现金流入小计', 450000, 400000],
                    ['经营活动现金流出小计', 350000, 300000],
                    ['经营活动产生的现金流量净额', 100000, 100000],
                    ['投资活动产生的现金流量净额', -50000, -40000],
                    ['筹资活动产生的现金流量净额', -30000, -20000]
                ]
            }
        }
    
    def test_classifier_initialization(self):
        """测试分类器初始化"""
        classifier = TableClassifier()
        
        # 验证关键词列表是否已初始化
        self.assertTrue(hasattr(classifier, 'balance_sheet_keywords'))
        self.assertTrue(hasattr(classifier, 'income_statement_keywords'))
        self.assertTrue(hasattr(classifier, 'cash_flow_keywords'))
    
    def test_table_classification(self):
        """测试表格分类功能"""
        classifier = TableClassifier()
        
        # 分类表格
        tables = [
            self.balance_sheet_data,
            self.income_statement_data,
            self.cash_flow_data
        ]
        
        classified_tables = classifier.classify(tables)
        
        # 验证分类结果
        self.assertEqual(len(classified_tables), 3)
        
        # 验证资产负债表分类
        self.assertEqual(classified_tables[0]['table_type'], 'balance_sheet')
        self.assertGreater(classified_tables[0]['confidence_score'], 0.5)
        
        # 验证利润表分类
        self.assertEqual(classified_tables[1]['table_type'], 'income_statement')
        self.assertGreater(classified_tables[1]['confidence_score'], 0.5)
        
        # 验证现金流量表分类
        self.assertEqual(classified_tables[2]['table_type'], 'cash_flow')
        self.assertGreater(classified_tables[2]['confidence_score'], 0.5)


class TasksTest(TestCase):
    """Celery任务测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        
        # 创建测试文件
        self.html_content = b'<html><body><table><tr><td>Test</td></tr></table></body></html>'
        self.test_file = SimpleUploadedFile(
            name='test_file.html',
            content=self.html_content,
            content_type='text/html'
        )
        
        # 创建SEC文件记录
        self.sec_file = SECFile.objects.create(
            user=self.user,
            file=self.test_file,
            file_name='test_file.html',
            file_size=len(self.html_content),
            file_type='html',
            status='pending'
        )
    
    @patch('extraction.tasks.HTMLProcessor')
    @patch('extraction.tasks.TableClassifier')
    def test_process_sec_file_task(self, mock_classifier, mock_html_processor):
        """测试处理SEC文件任务"""
        # 设置模拟对象
        mock_processor_instance = MagicMock()
        mock_html_processor.return_value = mock_processor_instance
        
        mock_classifier_instance = MagicMock()
        mock_classifier.return_value = mock_classifier_instance
        
        # 模拟处理结果
        mock_tables = [
            {
                'table_name': '资产负债表',
                'table_index': 0,
                'table_data': {
                    'headers': ['项目', '2023-12-31'],
                    'rows': [['资产总计', 1000000]]
                }
            }
        ]
        mock_processor_instance.process.return_value = mock_tables
        
        mock_classified_tables = [
            {
                'table_name': '资产负债表',
                'table_index': 0,
                'table_type': 'balance_sheet',
                'confidence_score': 0.95,
                'table_data': {
                    'headers': ['项目', '2023-12-31'],
                    'rows': [['资产总计', 1000000]]
                }
            }
        ]
        mock_classifier_instance.classify.return_value = mock_classified_tables
        
        # 执行任务
        result = process_sec_file(self.sec_file.id)
        
        # 验证结果
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['file_id'], self.sec_file.id)
        self.assertEqual(result['tables_count'], 1)
        
        # 验证文件状态
        updated_file = SECFile.objects.get(id=self.sec_file.id)
        self.assertEqual(updated_file.status, 'completed')
        
        # 验证表格是否创建
        tables = ExtractedTable.objects.filter(file=self.sec_file)
        self.assertEqual(tables.count(), 1)
        self.assertEqual(tables[0].table_type, 'balance_sheet')
    
    def tearDown(self):
        """清理测试环境"""
        # 删除测试文件
        if os.path.exists(self.sec_file.file.path):
            os.remove(self.sec_file.file.path)
