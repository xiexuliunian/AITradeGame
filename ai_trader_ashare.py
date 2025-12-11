"""
AI Trader for A-Share Market - A股市场AI交易员
"""
import json
import traceback
from typing import Dict
from openai import OpenAI, APIConnectionError, APIError

try:
    import requests
except ImportError:
    requests = None

class AShareAITrader:
    """A股市场AI交易员"""
    
    def __init__(self, provider_type: str, api_key: str, api_url: str, model_name: str):
        self.provider_type = provider_type.lower()
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
    
    def make_decision(self, market_state: Dict, portfolio: Dict, 
                     account_info: Dict) -> Dict:
        """做出交易决策：优先使用帝论三类买卖点的规则。
        若需要，可退回到LLM决策。
        """
        try:
            return self._make_decision_by_rules(market_state, portfolio, account_info)
        except Exception:
            # 回退到LLM
            prompt = self._build_ashare_prompt(market_state, portfolio, account_info)
            response = self._call_llm(prompt)
            decisions = self._parse_response(response)
            return decisions

    def _make_decision_by_rules(self, market_state: Dict, portfolio: Dict, account_info: Dict) -> Dict:
        """帝论：三类买卖点（流程化实现）
        流程（横盘→突破→趋势启动→脱离→回归修正→回调失败→趋势延续→涨幅够了→回到横盘）：
        - 第三类买点（突破横盘，趋势启动）：MA5>MA10>MA20 且 价格突破MA5或区间上沿，MACD>0。
        - 第一类买点（脱离后回归修正）：上行后回到均线带（MA10/MA20）附近企稳，结构未破坏。
        - 第二类买点（回调失败确认）：回踩后无法有效跌破MA10/MA20，RSI 45~60，继续上行。
        对应卖点：趋势破坏、冲高回落、止损退出。
        优先级：第三类买点 > 第一类买点 > 第二类买点（同一时刻仅择其一）。
        """
        decisions: Dict = {}
        positions = {pos['coin']: pos for pos in portfolio.get('positions', [])}

        for stock, data in market_state.items():
            price = data.get('price')
            ind = data.get('indicators', {})
            ma5 = ind.get('sma_5')
            ma10 = ind.get('sma_10')
            ma20 = ind.get('sma_20')
            rsi = ind.get('rsi_14')
            macd = ind.get('macd')

            # 若缺关键指标，则跳过
            if any(v is None for v in [price, ma5, ma10, ma20, rsi, macd]):
                decisions[stock] = { 'signal': 'hold' }
                continue

            has_pos = stock in positions
            qty_unit = 100
            # 资金与仓位控制：单票不超过总资金30%，最小买入1手
            cash = portfolio.get('cash', 0)
            max_buy_amount = account_info.get('initial_capital', 0) * 0.3
            target_amount = min(max_buy_amount, cash)
            buy_qty = int(target_amount // price // qty_unit * qty_unit)
            if buy_qty < 100:
                buy_qty = 0

            # 简化的近期高低判定（用MA区代替）
            # 横盘近似：均线粘合（MA20 与 MA10 接近），波动较小（用价格相对MA20偏离 < 3% 近似）
            consolidating = (abs(ma10 - ma20) / ma20 < 0.01) and (abs(price - ma20) / ma20 < 0.03)

            # 第三类买点：突破横盘，趋势启动（最高优先级）
            third_buy = (ma5 > ma10 > ma20) and (price > ma5) and (macd > 0)

            # 第一类买点：脱离后回归修正（回到均线带并企稳）
            first_buy = (ma5 >= ma10 >= ma20) and (abs(price - ma10) / ma10 < 0.01)

            # 第二类买点：回调失败（难以有效跌破均线，RSI中性偏强）
            second_buy = (abs(price - ma10) / ma10 < 0.01) and (45 <= rsi <= 60) and (ma5 >= ma10)

            break_trend = (price < ma20) and (macd < 0)
            rsi_cooling = (rsi > 70) and (price < ma5)

            pos = positions.get(stock)
            entry = pos['avg_price'] if pos else None
            stop_loss_hit = False
            if pos and entry:
                stop_loss_hit = (price <= entry * 0.95)

            # 决策
            if not has_pos:
                # 优先级顺序：第三 > 第一 > 第二
                if third_buy and buy_qty >= 100:
                    decisions[stock] = {
                        'signal': 'buy',
                        'quantity': buy_qty,
                        'profit_target': round(price * 1.10, 2),
                        'stop_loss': round(price * 0.95, 2),
                        'confidence': 0.8,
                        'justification': '第三类买点：突破横盘，趋势启动（均线多头+价格突破+MACD>0）'
                    }
                elif first_buy and buy_qty >= 100:
                    decisions[stock] = {
                        'signal': 'buy',
                        'quantity': buy_qty,
                        'profit_target': round(price * 1.08, 2),
                        'stop_loss': round(price * 0.96, 2),
                        'confidence': 0.7,
                        'justification': '第一类买点：脱离后回归修正，靠近MA10企稳'
                    }
                elif second_buy and buy_qty >= 100:
                    decisions[stock] = {
                        'signal': 'buy',
                        'quantity': buy_qty,
                        'profit_target': round(price * 1.06, 2),
                        'stop_loss': round(price * 0.94, 2),
                        'confidence': 0.6,
                        'justification': '第二类买点：回调失败确认，趋势延续'
                    }
                else:
                    decisions[stock] = { 'signal': 'hold' }
            else:
                sell_qty = int(pos['quantity'] // qty_unit * qty_unit)
                if sell_qty < 100:
                    sell_qty = int(pos['quantity'])  # 末端可小于100全部卖出

                if break_trend and sell_qty > 0:
                    decisions[stock] = {
                        'signal': 'sell',
                        'quantity': sell_qty,
                        'confidence': 0.8,
                        'justification': '第一类卖点：跌破MA20且MACD转负'
                    }
                elif rsi_cooling and sell_qty > 0:
                    decisions[stock] = {
                        'signal': 'sell',
                        'quantity': sell_qty,
                        'confidence': 0.7,
                        'justification': '第二类卖点：RSI>70后回落，价格跌破MA5'
                    }
                elif stop_loss_hit and sell_qty > 0:
                    decisions[stock] = {
                        'signal': 'sell',
                        'quantity': sell_qty,
                        'confidence': 0.9,
                        'justification': '第三类卖点：止损触发（-5%）'
                    }
                else:
                    decisions[stock] = { 'signal': 'hold' }

        return decisions
    
    def _build_ashare_prompt(self, market_state: Dict, portfolio: Dict, 
                            account_info: Dict) -> str:
        """构建A股市场交易提示词（强调帝论三类买卖点）"""
        prompt = f"""你是一位深谙帝论（趋势交易法）且熟悉中国A股规则的专业交易员。请严格依据帝论“三类买卖点”的思想进行交易决策，并输出JSON。

市场数据：
"""
        for stock, data in market_state.items():
            stock_name = data.get('name', stock)
            prompt += f"{stock} ({stock_name}): ¥{data['price']:.2f} ({data['change_24h']:+.2f}%)\n"
            if 'indicators' in data and data['indicators']:
                indicators = data['indicators']
                prompt += f"  MA5: ¥{indicators.get('sma_5', 0):.2f}, MA10: ¥{indicators.get('sma_10', 0):.2f}, MA20: ¥{indicators.get('sma_20', 0):.2f}, RSI: {indicators.get('rsi_14', 0):.1f}\n"
                prompt += f"  MACD: {indicators.get('macd', 0):.2f}, 7日涨跌: {indicators.get('price_change_7d', 0):.2f}%\n"
        
        prompt += f"""
账户状态：
- 初始资金：¥{account_info['initial_capital']:.2f}
- 总资产：¥{portfolio['total_value']:.2f}
- 可用资金：¥{portfolio['cash']:.2f}
- 总收益率：{account_info['total_return']:.2f}%

当前持仓：
"""
        if portfolio['positions']:
            for pos in portfolio['positions']:
                stock_code = pos['coin']  # 数据库中使用coin字段存储股票代码
                stock_name = ''
                if stock_code in market_state:
                    stock_name = market_state[stock_code].get('name', '')
                prompt += f"- {stock_code} ({stock_name}): {int(pos['quantity'])}股 @ ¥{pos['avg_price']:.2f}"
                if pos.get('current_price'):
                    pnl_pct = ((pos['current_price'] - pos['avg_price']) / pos['avg_price']) * 100
                    prompt += f" (当前¥{pos['current_price']:.2f}, {pnl_pct:+.2f}%)"
                prompt += "\n"
        else:
            prompt += "无持仓\n"
        
          prompt += """
A股交易规则（硬性约束）：
1. T+1制度：当天买入，次日才能卖出；避免当日反向操作。
2. 涨跌停：普通±10%，ST±5%，避免在已触及涨跌停价位下单。
3. 交易单位：买入必须为100股整数倍；卖出末端允许不足100股一次性清仓。
4. 费用：买入仅佣金（约0.03%，最低5元）；卖出佣金+印花税（0.1%）。
5. 无杠杆：仅做多，`side=long`。

帝论“三类买点/卖点”思想（用于决策判断）：
- 第一类买点（趋势突破）：均线多头排列（MA5>MA10>MA20）、价格突破关键位（如MA5或近期高点）且MACD为正，放量更佳。
- 第二类买点（回踩确认）：上行趋势中价格回踩至MA10/MA20附近企稳，RSI处于中性偏强（45~60），缩量回踩后再放量上行。
- 第三类买点（超跌反弹）：强势股调整后RSI低于30出现快速回升，或RSI回到>35伴随MACD金叉与阳线；适合小仓位试探。
- 第一类卖点（趋势破坏）：价格跌破MA20且MACD转负，趋势结构破坏，需减仓或清仓。
- 第二类卖点（冲高回落）：RSI>70后出现回落迹象（价格跌破MA5、放量长上影等），择机止盈。
- 第三类卖点（止损退出）：价格跌破最近关键低点或相对买入价-5%~-8%，坚决执行止损。

风险与仓位控制：
- 单票目标仓位不超过初始资金的30%，单次买入按100股整数倍；资金不足一手则`hold`。
- 止损遵循第三类卖点原则；利润目标与风险比至少1.5:1。

输出格式（仅JSON）：
```json
{
  "股票代码": {
    "signal": "buy|sell|hold",
    "quantity": 100,
    "profit_target": 15.50,
    "stop_loss": 13.20,
    "confidence": 0.75,
     "justification": "基于帝论第X类买/卖点的简短理由"
  }
}
```

注意：
- quantity 必须是100的整数倍
- signal只能是：buy（买入）、sell（卖出）、hold（持有）
- 已有持仓的可以sell，没有持仓的可以buy
- T+1约束：当日买入的股票不要在当天给出sell（返回hold或仅给出未来计划）
- 请严格按照JSON格式输出，不要包含其他内容

请分析并输出JSON：
"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        # OpenAI兼容的API（包括OpenAI、DeepSeek等）
        if self.provider_type in ['openai', 'azure_openai', 'deepseek']:
            return self._call_openai_api(prompt)
        elif self.provider_type == 'anthropic':
            return self._call_anthropic_api(prompt)
        elif self.provider_type == 'gemini':
            return self._call_gemini_api(prompt)
        else:
            # 默认使用OpenAI兼容API
            return self._call_openai_api(prompt)
    
    def _call_openai_api(self, prompt: str) -> str:
        """调用OpenAI兼容API"""
        try:
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                if '/v1' in base_url:
                    base_url = base_url.split('/v1')[0] + '/v1'
                else:
                    base_url = base_url + '/v1'
            
            client = OpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的中国A股交易员。请仅输出JSON格式的交易决策。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except APIConnectionError as e:
            error_msg = f"API连接失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except APIError as e:
            error_msg = f"API错误 ({e.status_code}): {e.message}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"OpenAI API调用失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(traceback.format_exc())
            raise Exception(error_msg)
    
    def _call_anthropic_api(self, prompt: str) -> str:
        """调用Anthropic Claude API"""
        if requests is None:
            raise Exception("requests library not available")
        
        try:
            
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                base_url = base_url + '/v1'
            
            url = f"{base_url}/messages"
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                "model": self.model_name,
                "max_tokens": 2000,
                "system": "你是一位专业的中国A股交易员。请仅输出JSON格式的交易决策。",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result['content'][0]['text']
            
        except Exception as e:
            error_msg = f"Anthropic API调用失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(traceback.format_exc())
            raise Exception(error_msg)
    
    def _call_gemini_api(self, prompt: str) -> str:
        """调用Google Gemini API"""
        if requests is None:
            raise Exception("requests library not available")
        
        try:
            
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                base_url = base_url + '/v1'
            
            url = f"{base_url}/{self.model_name}:generateContent"
            headers = {
                'Content-Type': 'application/json'
            }
            params = {'key': self.api_key}
            
            data = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"你是一位专业的中国A股交易员。请仅输出JSON格式的交易决策。\n\n{prompt}"
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2000
                }
            }
            
            response = requests.post(url, headers=headers, params=params, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
            
        except Exception as e:
            error_msg = f"Gemini API调用失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(traceback.format_exc())
            raise Exception(error_msg)
    
    def _parse_response(self, response: str) -> Dict:
        """解析响应"""
        response = response.strip()
        
        # 提取JSON
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            response = response.split('```')[1].split('```')[0]
        
        try:
            decisions = json.loads(response.strip())
            return decisions
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON解析失败: {e}")
            print(f"[DATA] 响应内容:\n{response}")
            return {}
