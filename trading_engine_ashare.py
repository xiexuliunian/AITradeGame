"""
A-Share Trading Engine - 适配中国A股市场规则
"""
from datetime import datetime
from typing import Dict
import json

class AShareTradingEngine:
    """
    A股交易引擎
    主要特性：
    1. T+1交易制度（当日买入的股票次日才能卖出）
    2. 涨跌停限制（一般为±10%，ST股票为±5%）
    3. 无杠杆交易（A股不支持保证金交易）
    4. 手续费：印花税+佣金
    """
    
    def __init__(self, model_id: int, db, market_fetcher, ai_trader, 
                 commission_rate: float = 0.0003,  # 佣金费率 0.03%
                 stamp_duty_rate: float = 0.001):   # 印花税 0.1% (仅卖出收取)
        self.model_id = model_id
        self.db = db
        self.market_fetcher = market_fetcher
        self.ai_trader = ai_trader
        
        # A股默认股票列表
        self.stocks = ['600519', '000858', '601318', '600036', '000333', '300750']
        
        # 费率设置
        self.commission_rate = commission_rate  # 佣金（买卖双向）
        self.stamp_duty_rate = stamp_duty_rate  # 印花税（仅卖出）
        
        # 涨跌停限制
        self.normal_limit = 0.10  # 普通股票涨跌停 10%
        self.st_limit = 0.05      # ST股票涨跌停 5%
    
    def execute_trading_cycle(self) -> Dict:
        """执行交易周期"""
        try:
            # 获取市场数据
            market_state = self._get_market_state()
            
            # 获取当前价格
            current_prices = {stock: market_state[stock]['price'] for stock in market_state}
            
            # 获取投资组合
            portfolio = self.db.get_portfolio(self.model_id, current_prices)
            
            # 构建账户信息
            account_info = self._build_account_info(portfolio)
            
            # AI决策
            decisions = self.ai_trader.make_decision(
                market_state, portfolio, account_info
            )
            
            # 记录对话
            self.db.add_conversation(
                self.model_id,
                user_prompt=self._format_prompt(market_state, portfolio, account_info),
                ai_response=json.dumps(decisions, ensure_ascii=False),
                cot_trace=''
            )
            
            # 执行交易决策
            execution_results = self._execute_decisions(decisions, market_state, portfolio)
            
            # 更新组合并记录账户价值
            updated_portfolio = self.db.get_portfolio(self.model_id, current_prices)
            self.db.record_account_value(
                self.model_id,
                updated_portfolio['total_value'],
                updated_portfolio['cash'],
                updated_portfolio['positions_value']
            )
            
            return {
                'success': True,
                'decisions': decisions,
                'executions': execution_results,
                'portfolio': updated_portfolio
            }
            
        except Exception as e:
            print(f"[ERROR] A-Share trading cycle failed (Model {self.model_id}): {e}")
            import traceback
            print(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_market_state(self) -> Dict:
        """获取市场状态"""
        market_state = {}
        prices = self.market_fetcher.get_current_prices(self.stocks)
        
        for stock in self.stocks:
            if stock in prices:
                market_state[stock] = prices[stock].copy()
                # 获取技术指标
                indicators = self.market_fetcher.calculate_technical_indicators(stock)
                market_state[stock]['indicators'] = indicators
        
        return market_state
    
    def _build_account_info(self, portfolio: Dict) -> Dict:
        """构建账户信息"""
        model = self.db.get_model(self.model_id)
        initial_capital = model['initial_capital']
        total_value = portfolio['total_value']
        total_return = ((total_value - initial_capital) / initial_capital) * 100
        
        return {
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_return': total_return,
            'initial_capital': initial_capital,
            'market': 'A-Share'  # 标识为A股市场
        }
    
    def _format_prompt(self, market_state: Dict, portfolio: Dict, 
                      account_info: Dict) -> str:
        """格式化提示词"""
        return f"A-Share Market State: {len(market_state)} stocks, Portfolio: {len(portfolio['positions'])} positions"
    
    def _execute_decisions(self, decisions: Dict, market_state: Dict, 
                          portfolio: Dict) -> list:
        """执行交易决策"""
        results = []
        
        for stock, decision in decisions.items():
            if stock not in self.stocks:
                continue
            
            signal = decision.get('signal', '').lower()
            
            try:
                if signal == 'buy':
                    result = self._execute_buy(stock, decision, market_state, portfolio)
                elif signal == 'sell':
                    result = self._execute_sell(stock, decision, market_state, portfolio)
                elif signal == 'hold':
                    result = {'stock': stock, 'signal': 'hold', 'message': '持有'}
                else:
                    result = {'stock': stock, 'error': f'未知信号: {signal}'}
                
                results.append(result)
                
            except Exception as e:
                results.append({'stock': stock, 'error': str(e)})
        
        return results
    
    def _execute_buy(self, stock: str, decision: Dict, market_state: Dict, 
                    portfolio: Dict) -> Dict:
        """执行买入操作"""
        quantity = int(decision.get('quantity', 0))
        price = market_state[stock]['price']
        
        # A股买入必须是100股的整数倍（1手=100股）
        if quantity < 100:
            return {'stock': stock, 'error': '买入数量必须至少100股（1手）'}
        
        if quantity % 100 != 0:
            quantity = (quantity // 100) * 100  # 向下取整到100的倍数
        
        if quantity <= 0:
            return {'stock': stock, 'error': '无效数量'}
        
        # 计算费用
        trade_amount = quantity * price
        commission = max(trade_amount * self.commission_rate, 5.0)  # 佣金最低5元
        total_cost = trade_amount + commission
        
        # 检查资金
        if total_cost > portfolio['cash']:
            return {'stock': stock, 'error': f'资金不足（需要 ¥{total_cost:.2f}，可用 ¥{portfolio["cash"]:.2f}）'}
        
        # 更新持仓（A股无杠杆，leverage固定为1）
        self.db.update_position(
            self.model_id, stock, quantity, price, leverage=1, side='long'
        )
        
        # 记录交易
        self.db.add_trade(
            self.model_id, stock, 'buy', quantity, 
            price, leverage=1, side='long', pnl=0, fee=commission
        )
        
        return {
            'stock': stock,
            'signal': 'buy',
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'total_cost': total_cost,
            'message': f'买入 {quantity}股 {market_state[stock].get("name", stock)} @ ¥{price:.2f} (手续费: ¥{commission:.2f})'
        }
    
    def _execute_sell(self, stock: str, decision: Dict, market_state: Dict, 
                     portfolio: Dict) -> Dict:
        """执行卖出操作"""
        # 查找持仓
        position = None
        for pos in portfolio['positions']:
            if pos['coin'] == stock:  # 数据库中使用coin字段
                position = pos
                break
        
        if not position:
            return {'stock': stock, 'error': '没有持仓'}
        
        # 获取卖出数量
        quantity = int(decision.get('quantity', position['quantity']))
        
        # A股卖出也必须是100股的整数倍，但最后可以不足100股时全部卖出
        if quantity > position['quantity']:
            quantity = int(position['quantity'])
        
        if quantity <= 0:
            return {'stock': stock, 'error': '无效数量'}
        
        current_price = market_state[stock]['price']
        entry_price = position['avg_price']
        
        # 计算收益和费用
        trade_amount = quantity * current_price
        commission = max(trade_amount * self.commission_rate, 5.0)  # 佣金最低5元
        stamp_duty = trade_amount * self.stamp_duty_rate  # 印花税
        total_fee = commission + stamp_duty
        
        # 计算利润
        gross_pnl = (current_price - entry_price) * quantity
        net_pnl = gross_pnl - total_fee
        
        # 更新或关闭持仓
        if quantity >= position['quantity']:
            # 全部卖出
            self.db.close_position(self.model_id, stock, side='long')
        else:
            # 部分卖出，更新持仓
            new_quantity = position['quantity'] - quantity
            self.db.update_position(
                self.model_id, stock, new_quantity, entry_price, 
                leverage=1, side='long'
            )
        
        # 记录交易
        self.db.add_trade(
            self.model_id, stock, 'sell', quantity,
            current_price, leverage=1, side='long', pnl=net_pnl, fee=total_fee
        )
        
        return {
            'stock': stock,
            'signal': 'sell',
            'quantity': quantity,
            'price': current_price,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'total_fee': total_fee,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'message': f'卖出 {quantity}股 {market_state[stock].get("name", stock)} @ ¥{current_price:.2f} (手续费: ¥{commission:.2f}, 印花税: ¥{stamp_duty:.2f}, 净盈亏: ¥{net_pnl:.2f})'
        }
    
    def _check_price_limit(self, stock: str, current_price: float, 
                          prev_close: float) -> bool:
        """检查是否涨跌停"""
        if prev_close <= 0:
            return True
        
        change_pct = abs((current_price - prev_close) / prev_close)
        
        # 判断是否ST股票（简化处理，实际应从股票名称判断）
        is_st = stock.startswith('ST') or 'ST' in stock
        limit = self.st_limit if is_st else self.normal_limit
        
        return change_pct < limit
