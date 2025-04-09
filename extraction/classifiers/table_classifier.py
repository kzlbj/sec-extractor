import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class TableClassifier:
    """表格分类器，用于识别财务报表类型"""
    
    def __init__(self):
        """初始化表格分类器"""
        # 资产负债表关键词
        self.balance_sheet_keywords = [
            'balance sheet', 'assets', 'liabilities', 'equity', 
            'current assets', 'non-current assets', 'current liabilities', 
            'stockholders', 'shareholders',
            '资产负债表', '资产', '负债', '权益', '流动资产', '非流动资产', '流动负债', '股东'
        ]
        
        # 利润表关键词
        self.income_statement_keywords = [
            'income statement', 'statement of income', 'profit', 'loss', 
            'revenue', 'sales', 'expense', 'earnings', 'net income',
            '利润表', '损益表', '收入', '销售', '费用', '盈利', '净利润'
        ]
        
        # 现金流量表关键词
        self.cash_flow_keywords = [
            'cash flow', 'operating activities', 'investing activities', 
            'financing activities', 'cash and cash equivalents',
            '现金流量表', '经营活动', '投资活动', '筹资活动', '现金及现金等价物'
        ]
    
    def classify(self, tables):
        """
        对表格进行分类
        
        参数:
            tables (list): 表格列表，每个表格是一个字典
            
        返回:
            list: 带有类型标签的表格列表
        """
        classified_tables = []
        
        for table in tables:
            table_type = self._determine_table_type(table)
            
            # 添加表格类型
            table['table_type'] = table_type
            
            # 计算置信度分数
            confidence_score = self._calculate_confidence_score(table, table_type)
            table['confidence_score'] = confidence_score
            
            classified_tables.append(table)
        
        return classified_tables
    
    def _determine_table_type(self, table):
        """
        确定表格类型
        
        参数:
            table (dict): 表格数据
            
        返回:
            str: 表格类型
        """
        # 提取表格名称和内容文本
        table_name = table.get('table_name', '').lower()
        
        # 提取表格内容
        table_content = self._extract_table_content(table)
        
        # 计算各类型的得分
        balance_sheet_score = self._calculate_keyword_score(
            table_name + ' ' + table_content, 
            self.balance_sheet_keywords
        )
        
        income_statement_score = self._calculate_keyword_score(
            table_name + ' ' + table_content, 
            self.income_statement_keywords
        )
        
        cash_flow_score = self._calculate_keyword_score(
            table_name + ' ' + table_content, 
            self.cash_flow_keywords
        )
        
        # 判断表格类型
        if balance_sheet_score > income_statement_score and balance_sheet_score > cash_flow_score:
            return 'balance_sheet'
        elif income_statement_score > balance_sheet_score and income_statement_score > cash_flow_score:
            return 'income_statement'
        elif cash_flow_score > balance_sheet_score and cash_flow_score > income_statement_score:
            return 'cash_flow'
        else:
            # 模式识别
            if self._match_balance_sheet_pattern(table):
                return 'balance_sheet'
            elif self._match_income_statement_pattern(table):
                return 'income_statement'
            elif self._match_cash_flow_pattern(table):
                return 'cash_flow'
            else:
                return 'unknown'
    
    def _extract_table_content(self, table):
        """提取表格内容文本"""
        content = []
        
        # 添加表头
        if 'headers' in table.get('table_data', {}):
            content.extend(table['table_data']['headers'])
        
        # 添加第一列（通常是项目名称）
        if 'rows' in table.get('table_data', {}):
            for row in table['table_data']['rows']:
                if row and len(row) > 0:
                    content.append(row[0])
        
        return ' '.join(str(item) for item in content if item)
    
    def _calculate_keyword_score(self, text, keywords):
        """计算关键词得分"""
        text = text.lower()
        score = 0
        
        for keyword in keywords:
            keyword = keyword.lower()
            count = text.count(keyword)
            
            # 根据关键词出现次数和长度加权
            score += count * len(keyword)
        
        return score
    
    def _calculate_confidence_score(self, table, table_type):
        """计算分类置信度分数"""
        if table_type == 'unknown':
            return 0.0
        
        # 提取表格内容
        table_name = table.get('table_name', '').lower()
        table_content = self._extract_table_content(table)
        combined_text = table_name + ' ' + table_content
        
        # 根据表格类型获取关键词
        if table_type == 'balance_sheet':
            keywords = self.balance_sheet_keywords
        elif table_type == 'income_statement':
            keywords = self.income_statement_keywords
        elif table_type == 'cash_flow':
            keywords = self.cash_flow_keywords
        else:
            return 0.0
        
        # 计算匹配的关键词数量
        matched_keywords = sum(1 for keyword in keywords if keyword.lower() in combined_text)
        
        # 计算置信度分数（0.0 - 1.0）
        confidence = min(1.0, matched_keywords / (len(keywords) * 0.3))
        
        # 基于模式匹配提高置信度
        if table_type == 'balance_sheet' and self._match_balance_sheet_pattern(table):
            confidence = max(confidence, 0.7)
        elif table_type == 'income_statement' and self._match_income_statement_pattern(table):
            confidence = max(confidence, 0.7)
        elif table_type == 'cash_flow' and self._match_cash_flow_pattern(table):
            confidence = max(confidence, 0.7)
        
        return confidence
    
    def _match_balance_sheet_pattern(self, table):
        """匹配资产负债表模式"""
        if 'table_data' not in table or 'rows' not in table['table_data']:
            return False
        
        # 资产负债表通常有资产=负债+权益的特点
        rows_text = ' '.join(str(row[0]) for row in table['table_data']['rows'] if row and len(row) > 0)
        rows_text = rows_text.lower()
        
        # 检查是否包含资产和负债
        has_assets = any(keyword in rows_text for keyword in ['assets', 'asset', '资产'])
        has_liabilities = any(keyword in rows_text for keyword in ['liabilities', 'liability', '负债'])
        
        return has_assets and has_liabilities
    
    def _match_income_statement_pattern(self, table):
        """匹配利润表模式"""
        if 'table_data' not in table or 'rows' not in table['table_data']:
            return False
        
        # 利润表通常有收入、成本和利润的结构
        rows_text = ' '.join(str(row[0]) for row in table['table_data']['rows'] if row and len(row) > 0)
        rows_text = rows_text.lower()
        
        # 检查是否包含收入和利润
        has_revenue = any(keyword in rows_text for keyword in ['revenue', 'sales', 'income', '收入', '销售'])
        has_profit = any(keyword in rows_text for keyword in ['profit', 'earnings', 'net income', '利润', '盈利'])
        
        return has_revenue and has_profit
    
    def _match_cash_flow_pattern(self, table):
        """匹配现金流量表模式"""
        if 'table_data' not in table or 'rows' not in table['table_data']:
            return False
        
        # 现金流量表通常有经营、投资和筹资活动的分类
        rows_text = ' '.join(str(row[0]) for row in table['table_data']['rows'] if row and len(row) > 0)
        rows_text = rows_text.lower()
        
        # 检查是否包含现金流量的三个主要类别
        has_operating = any(keyword in rows_text for keyword in ['operating', 'operations', '经营'])
        has_investing = any(keyword in rows_text for keyword in ['investing', 'investment', '投资'])
        has_financing = any(keyword in rows_text for keyword in ['financing', 'finance', '筹资', '融资'])
        
        return has_operating or (has_investing and has_financing)