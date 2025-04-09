import os
import logging
import time
import traceback
import pandas as pd
from arelle import ModelManager, ModelXbrl
from arelle.Cntlr import Cntlr

logger = logging.getLogger(__name__)


class XBRLProcessor:
    """XBRL文件处理器，利用Arelle库处理XBRL文档"""
    
    def __init__(self):
        """初始化XBRL处理器"""
        try:
            # 初始化Arelle控制器
            self.controller = Cntlr()
            self.controller.startLogging(logFileName=os.path.join('logs', 'arelle.log'))
            logger.info("成功初始化XBRL处理器")
        except Exception as e:
            logger.critical(f"XBRL处理器初始化失败: {str(e)}")
            raise RuntimeError(f"无法初始化XBRL处理器: {str(e)}") from e
    
    def process(self, file_path):
        """
        处理XBRL文件并提取表格数据
        
        参数:
            file_path (str): XBRL文件路径
        
        返回:
            list: 提取的表格列表，每个表格是一个字典
        """
        start_time = time.time()
        logger.info(f"开始处理XBRL文件: {file_path}")
        
        if not os.path.exists(file_path):
            error_msg = f"文件不存在: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            # 加载XBRL文档
            model_manager = ModelManager.initialize(self.controller)
            xbrl = ModelXbrl.load(model_manager, file_path)
            
            if xbrl is None:
                error_msg = f"无法加载XBRL文件: {file_path}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 提取财务报表
            financial_statements = self._extract_financial_statements(xbrl)
            
            # 关闭XBRL文档
            try:
                xbrl.close()
            except Exception as e:
                logger.warning(f"关闭XBRL文档时出错 (非致命): {str(e)}")
            
            processing_time = time.time() - start_time
            logger.info(f"成功处理XBRL文件: {file_path}，提取了 {len(financial_statements)} 个表格，耗时: {processing_time:.2f}秒")
            return financial_statements
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_details = traceback.format_exc()
            logger.exception(f"处理XBRL文件 {file_path} 时出错 (耗时: {processing_time:.2f}秒): {str(e)}\n{error_details}")
            raise RuntimeError(f"XBRL文件处理失败: {str(e)}") from e
    
    def _extract_financial_statements(self, xbrl):
        """
        从XBRL文档中提取财务报表
        
        参数:
            xbrl (ModelXbrl): 加载的XBRL模型
        
        返回:
            list: 提取的财务报表列表
        """
        statements = []
        
        try:
            # 获取表示期间（财务报告的时间范围）
            contexts = self._analyze_contexts(xbrl)
            logger.debug(f"提取了 {len(contexts)} 个上下文")
            
            # 获取所有概念/元素
            concepts = xbrl.modelXbrl.qnameConcepts
            logger.debug(f"提取了 {len(concepts)} 个概念")
            
            # 提取资产负债表
            try:
                balance_sheet = self._extract_balance_sheet(xbrl, contexts, concepts)
                if balance_sheet:
                    statements.append({
                        'table_name': '资产负债表',
                        'table_data': balance_sheet
                    })
                    logger.info("成功提取资产负债表")
                else:
                    logger.warning("未能提取资产负债表，可能不存在或格式不支持")
            except Exception as e:
                logger.error(f"提取资产负债表时出错: {str(e)}")
            
            # 提取利润表
            try:
                income_statement = self._extract_income_statement(xbrl, contexts, concepts)
                if income_statement:
                    statements.append({
                        'table_name': '利润表',
                        'table_data': income_statement
                    })
                    logger.info("成功提取利润表")
                else:
                    logger.warning("未能提取利润表，可能不存在或格式不支持")
            except Exception as e:
                logger.error(f"提取利润表时出错: {str(e)}")
            
            # 提取现金流量表
            try:
                cash_flow = self._extract_cash_flow_statement(xbrl, contexts, concepts)
                if cash_flow:
                    statements.append({
                        'table_name': '现金流量表',
                        'table_data': cash_flow
                    })
                    logger.info("成功提取现金流量表")
                else:
                    logger.warning("未能提取现金流量表，可能不存在或格式不支持")
            except Exception as e:
                logger.error(f"提取现金流量表时出错: {str(e)}")
            
            if not statements:
                logger.warning("未能从XBRL文档中提取任何财务报表")
            
            return statements
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.exception(f"提取财务报表时出错: {str(e)}\n{error_details}")
            return []
    
    def _analyze_contexts(self, xbrl):
        """分析XBRL上下文，确定报告期间"""
        contexts = {}
        
        try:
            for context in xbrl.contexts.values():
                try:
                    if context.isInstantPeriod:
                        # 即时上下文（如资产负债表日期）
                        end_date = context.endDatetime.strftime('%Y-%m-%d')
                        contexts[context.id] = {
                            'type': 'instant',
                            'date': end_date
                        }
                    elif context.isStartEndPeriod:
                        # 期间上下文（如利润表期间）
                        start_date = context.startDatetime.strftime('%Y-%m-%d')
                        end_date = context.endDatetime.strftime('%Y-%m-%d')
                        contexts[context.id] = {
                            'type': 'period',
                            'start_date': start_date,
                            'end_date': end_date
                        }
                except Exception as e:
                    logger.debug(f"处理上下文 {context.id} 时出错: {str(e)}")
                    continue
            
            if not contexts:
                logger.warning("未能提取任何有效的报告期间上下文")
            
            return contexts
        except Exception as e:
            logger.error(f"分析上下文时出错: {str(e)}")
            return {}
    
    def _extract_balance_sheet(self, xbrl, contexts, concepts):
        """提取资产负债表"""
        # 资产负债表关键项目
        bs_items = [
            'Assets', 'AssetsCurrent', 'AssetsNoncurrent',
            'Liabilities', 'LiabilitiesCurrent', 'LiabilitiesNoncurrent',
            'StockholdersEquity', 'LiabilitiesAndStockholdersEquity'
        ]
        
        return self._extract_statement_data(xbrl, contexts, concepts, bs_items)
    
    def _extract_income_statement(self, xbrl, contexts, concepts):
        """提取利润表"""
        # 利润表关键项目
        is_items = [
            'Revenues', 'CostOfRevenue', 'GrossProfit',
            'OperatingExpenses', 'OperatingIncomeLoss',
            'IncomeTaxExpenseBenefit', 'NetIncomeLoss',
            'EarningsPerShareBasic', 'EarningsPerShareDiluted'
        ]
        
        return self._extract_statement_data(xbrl, contexts, concepts, is_items)
    
    def _extract_cash_flow_statement(self, xbrl, contexts, concepts):
        """提取现金流量表"""
        # 现金流量表关键项目
        cf_items = [
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInInvestingActivities',
            'NetCashProvidedByUsedInFinancingActivities',
            'CashAndCashEquivalentsPeriodIncreaseDecrease',
            'CashAndCashEquivalentsAtCarryingValue'
        ]
        
        return self._extract_statement_data(xbrl, contexts, concepts, cf_items)
    
    def _extract_statement_data(self, xbrl, contexts, concepts, items):
        """
        提取报表数据
        
        参数:
            xbrl (ModelXbrl): XBRL模型
            contexts (dict): 上下文信息
            concepts (dict): 概念/元素字典
            items (list): 要提取的项目列表
        
        返回:
            dict: 提取的报表数据
        """
        statement_data = {
            'headers': [],
            'rows': []
        }
        
        # 获取所有与指定项目相关的事实
        relevant_facts = []
        for fact in xbrl.facts:
            if fact.concept is not None and fact.concept.name in items:
                relevant_facts.append(fact)
        
        if not relevant_facts:
            return None
        
        # 提取时间列（表头）
        periods = set()
        for fact in relevant_facts:
            if fact.contextID in contexts:
                if contexts[fact.contextID]['type'] == 'instant':
                    periods.add(contexts[fact.contextID]['date'])
                elif contexts[fact.contextID]['type'] == 'period':
                    periods.add(contexts[fact.contextID]['end_date'])
        
        # 排序期间
        sorted_periods = sorted(periods)
        statement_data['headers'] = ['项目'] + sorted_periods
        
        # 提取每个项目的数据
        for item in items:
            item_values = [''] * len(sorted_periods)
            item_facts = [f for f in relevant_facts if f.concept.name == item]
            
            for fact in item_facts:
                if fact.contextID in contexts:
                    period_info = contexts[fact.contextID]
                    period_date = period_info['date'] if period_info['type'] == 'instant' else period_info['end_date']
                    
                    if period_date in sorted_periods:
                        period_index = sorted_periods.index(period_date)
                        # 处理数值和单位
                        value = fact.value
                        unit = fact.unit.value if fact.unit is not None else None
                        
                        # 尝试转换为数值
                        try:
                            value = float(value)
                            # 根据单位调整
                            if unit == 'USD-per-shares':
                                pass  # 保持原样
                            elif unit == 'shares':
                                value = int(value)
                            else:
                                # 默认以百万为单位
                                value = value / 1000000
                            item_values[period_index] = value
                        except (ValueError, TypeError):
                            item_values[period_index] = value
            
            # 获取项目的标签/名称
            item_concept = None
            for qname, concept in concepts.items():
                if concept.name == item:
                    item_concept = concept
                    break
            
            item_label = item
            if item_concept is not None and hasattr(item_concept, 'label'):
                labels = item_concept.label()
                if labels:
                    item_label = labels[0].text
            
            row_data = [item_label] + item_values
            statement_data['rows'].append(row_data)
        
        return statement_data 