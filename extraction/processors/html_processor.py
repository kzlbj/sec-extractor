import os
import re
import logging
import time
import traceback
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HTMLProcessor:
    """HTML文件处理器，用于处理SEC HTML文件中的表格"""
    
    def __init__(self):
        """初始化HTML处理器"""
        logger.info("成功初始化HTML处理器")
    
    def process(self, file_path):
        """
        处理HTML文件并提取表格数据
        
        参数:
            file_path (str): HTML文件路径
            
        返回:
            list: 提取的表格列表，每个表格是一个字典
        """
        start_time = time.time()
        logger.info(f"开始处理HTML文件: {file_path}")
        
        if not os.path.exists(file_path):
            error_msg = f"文件不存在: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            # 读取HTML文件
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    html_content = file.read()
            except UnicodeDecodeError:
                # 尝试使用不同的编码
                logger.warning(f"使用UTF-8解码失败，尝试使用其他编码...")
                encodings = ['latin-1', 'iso-8859-1', 'cp1252']
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as file:
                            html_content = file.read()
                            logger.info(f"成功使用 {encoding} 编码读取文件")
                            break
                    except Exception:
                        continue
                else:
                    error_msg = f"无法读取HTML文件，所有编码尝试失败: {file_path}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            # 使用BeautifulSoup解析HTML
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                logger.debug(f"成功解析HTML文档，文档大小: {len(html_content)} 字节")
            except Exception as e:
                error_msg = f"HTML解析失败: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e
            
            # 提取所有表格
            tables = self._extract_tables(soup)
            
            processing_time = time.time() - start_time
            logger.info(f"成功处理HTML文件: {file_path}，提取了 {len(tables)} 个表格，耗时: {processing_time:.2f}秒")
            return tables
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_details = traceback.format_exc()
            logger.exception(f"处理HTML文件 {file_path} 时出错 (耗时: {processing_time:.2f}秒): {str(e)}\n{error_details}")
            raise RuntimeError(f"HTML文件处理失败: {str(e)}") from e
    
    def _extract_tables(self, soup):
        """
        从HTML中提取所有表格
        
        参数:
            soup (BeautifulSoup): 解析的HTML内容
            
        返回:
            list: 提取的表格列表
        """
        tables = []
        
        try:
            # 查找所有表格元素
            html_tables = soup.find_all('table')
            logger.debug(f"在HTML文档中找到 {len(html_tables)} 个表格元素")
            
            financial_tables_count = 0
            for idx, table in enumerate(html_tables):
                try:
                    # 判断表格是否为财务报表
                    if not self._is_financial_table(table):
                        logger.debug(f"表格 #{idx} 不是财务报表，跳过")
                        continue
                    
                    financial_tables_count += 1
                    logger.debug(f"处理财务报表表格 #{idx}")
                    
                    # 处理表格
                    processed_table = self._process_table(table)
                    
                    if processed_table:
                        # 尝试确定表格名称
                        table_name = self._extract_table_name(table)
                        
                        tables.append({
                            'table_name': table_name,
                            'table_index': idx,
                            'table_data': processed_table
                        })
                        logger.info(f"成功提取表格 #{idx}: {table_name}")
                    else:
                        logger.warning(f"表格 #{idx} 处理结果为空，跳过")
                except Exception as e:
                    logger.warning(f"处理表格 #{idx} 时出错: {str(e)}")
                    continue
            
            logger.info(f"在 {len(html_tables)} 个表格中识别出 {financial_tables_count} 个财务报表，成功提取 {len(tables)} 个")
            return tables
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.exception(f"提取表格时出错: {str(e)}\n{error_details}")
            return []
    
    def _is_financial_table(self, table):
        """
        判断表格是否为财务报表表格
        
        参数:
            table (Tag): BeautifulSoup表格元素
            
        返回:
            bool: 是否为财务报表表格
        """
        # 检查表格的行数和列数
        rows = table.find_all('tr')
        if len(rows) < 3:  # 表格太小，不太可能是财务报表
            return False
        
        # 检查表格内容
        text = table.get_text().lower()
        
        # 检查是否包含财务报表常见关键词
        financial_keywords = [
            'assets', 'liabilities', 'equity', 'revenue', 'income', 
            'expense', 'cash', 'flow', 'balance', 'statement',
            '资产', '负债', '权益', '收入', '利润', '费用', '现金', '流量', '报表'
        ]
        
        for keyword in financial_keywords:
            if keyword in text:
                return True
        
        return False
    
    def _extract_table_name(self, table):
        """
        尝试提取表格名称
        
        参数:
            table (Tag): BeautifulSoup表格元素
            
        返回:
            str: 表格名称
        """
        # 首先，检查表格的caption
        caption = table.find('caption')
        if caption:
            return caption.get_text().strip()
        
        # 查找表格前面的标题元素
        prev_element = table.find_previous(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div'])
        if prev_element and prev_element.get_text().strip():
            text = prev_element.get_text().strip()
            # 判断是否为可能的表格标题
            if len(text) < 200 and any(keyword in text.lower() for keyword in 
                                      ['statement', 'table', 'report', '表', '报表', '报告']):
                return text
        
        # 查找表格内第一行是否为标题
        first_row = table.find('tr')
        if first_row:
            th_cells = first_row.find_all('th')
            if th_cells and len(th_cells) > 0:
                colspan_count = sum(int(th.get('colspan', 1)) for th in th_cells)
                if colspan_count > 1:  # 跨列标题可能是表格名称
                    return th_cells[0].get_text().strip()
        
        # 没有找到合适的标题
        return "未命名表格"
    
    def _process_table(self, table):
        """
        处理HTML表格，提取结构化数据
        
        参数:
            table (Tag): BeautifulSoup表格元素
            
        返回:
            dict: 处理后的表格数据
        """
        # 处理合并单元格和表头
        return self._handle_complex_table(table)
    
    def _handle_complex_table(self, table):
        """
        处理复杂表格（含合并单元格）
        
        参数:
            table (Tag): BeautifulSoup表格元素
            
        返回:
            dict: 处理后的表格数据
        """
        rows = table.find_all('tr')
        if not rows:
            return None
        
        # 确定表格的最大列数
        max_cols = 0
        for row in rows:
            cols = 0
            for cell in row.find_all(['td', 'th']):
                colspan = int(cell.get('colspan', 1))
                cols += colspan
            max_cols = max(max_cols, cols)
        
        # 初始化表格矩阵
        matrix = [[None for _ in range(max_cols)] for _ in range(len(rows))]
        
        # 填充表格矩阵
        for i, row in enumerate(rows):
            col_idx = 0
            for cell in row.find_all(['td', 'th']):
                # 跳过已填充的单元格
                while col_idx < max_cols and matrix[i][col_idx] is not None:
                    col_idx += 1
                
                if col_idx >= max_cols:
                    break
                
                # 获取单元格内容
                cell_text = cell.get_text().strip()
                cell_text = re.sub(r'\s+', ' ', cell_text)  # 规范化空白
                
                # 处理合并单元格
                rowspan = int(cell.get('rowspan', 1))
                colspan = int(cell.get('colspan', 1))
                
                # 填充矩阵
                for r in range(i, min(i + rowspan, len(rows))):
                    for c in range(col_idx, min(col_idx + colspan, max_cols)):
                        if r == i and c == col_idx:
                            matrix[r][c] = cell_text
                        else:
                            matrix[r][c] = ''  # 标记为已填充
                
                col_idx += colspan
        
        # 清理空值
        for i in range(len(matrix)):
            for j in range(len(matrix[i])):
                if matrix[i][j] is None:
                    matrix[i][j] = ''
        
        # 识别表头和数据行
        header_rows = self._identify_header_rows(matrix)
        
        if not header_rows:
            # 如果没有识别出表头，默认第一行为表头
            headers = matrix[0]
            data_rows = matrix[1:]
        else:
            # 合并多行表头
            headers = self._merge_header_rows([matrix[i] for i in header_rows])
            data_rows = [matrix[i] for i in range(len(matrix)) if i not in header_rows]
        
        # 尝试将数值转换为浮点数
        data_rows = self._convert_numeric_values(data_rows)
        
        return {
            'headers': headers,
            'rows': data_rows
        }
    
    def _identify_header_rows(self, matrix):
        """识别表头行"""
        header_rows = []
        
        # 检查前几行
        for i in range(min(3, len(matrix))):
            row = matrix[i]
            
            # 计算包含数字的单元格比例
            num_cells = sum(1 for cell in row if self._is_numeric(cell))
            if num_cells / len(row) < 0.3:  # 如果数字比例低，可能是表头
                # 检查单元格是否包含th或header类
                header_rows.append(i)
        
        return header_rows
    
    def _merge_header_rows(self, header_rows):
        """合并多行表头"""
        if not header_rows:
            return []
        
        if len(header_rows) == 1:
            return header_rows[0]
        
        # 合并多行表头
        merged_header = []
        for col in range(len(header_rows[0])):
            header_parts = []
            for row in header_rows:
                if col < len(row) and row[col]:
                    header_parts.append(row[col])
            
            merged_header.append(' '.join(header_parts))
        
        return merged_header
    
    def _convert_numeric_values(self, data_rows):
        """尝试将数值转换为浮点数"""
        converted_rows = []
        
        for row in data_rows:
            converted_row = []
            for cell in row:
                # 尝试转换为数值
                converted_cell = self._try_convert_to_number(cell)
                converted_row.append(converted_cell)
            
            converted_rows.append(converted_row)
        
        return converted_rows
    
    def _try_convert_to_number(self, text):
        """尝试将文本转换为数字"""
        # 如果为空，直接返回
        if not text:
            return text
        
        # 删除千位分隔符和货币符号
        cleaned_text = re.sub(r'[,$€¥\s]', '', text)
        
        # 处理括号表示的负数
        if cleaned_text.startswith('(') and cleaned_text.endswith(')'):
            cleaned_text = '-' + cleaned_text[1:-1]
        
        # 尝试转换为数字
        try:
            # 尝试转换为整数
            if '.' not in cleaned_text:
                return int(cleaned_text)
            # 尝试转换为浮点数
            return float(cleaned_text)
        except ValueError:
            # 无法转换，保留原文本
            return text
    
    def _is_numeric(self, text):
        """判断文本是否为数字"""
        if not text:
            return False
        
        # 删除千位分隔符和货币符号
        cleaned_text = re.sub(r'[,$€¥\s]', '', text)
        
        # 处理括号表示的负数
        if cleaned_text.startswith('(') and cleaned_text.endswith(')'):
            cleaned_text = '-' + cleaned_text[1:-1]
        
        # 尝试转换为数字
        try:
            float(cleaned_text)
            return True
        except ValueError:
            return False 