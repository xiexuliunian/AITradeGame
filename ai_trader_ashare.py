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
        """做出交易决策（LLM-only）：严格依据两份PDF核心思想，尤其帝论三类买卖点"""
        prompt = self._build_ashare_prompt(market_state, portfolio, account_info)
        response_text = self._call_llm(prompt)
        return self._parse_response(response_text)

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
        sp = account_info.get('strategy_params', {})
        # 参数默认值（简易交易系统）
        pull_tol = sp.get('ma', {}).get('pullback_tolerance', 0.01)
        rsi_buy_low = sp.get('rsi', {}).get('buy_low', 30)
        rsi_neu_low = sp.get('rsi', {}).get('neutral_low', 45)
        rsi_neu_high = sp.get('rsi', {}).get('neutral_high', 60)
        rsi_sell_high = sp.get('rsi', {}).get('sell_high', 70)
        pos_limit_pct = sp.get('risk', {}).get('position_limit_pct', 0.30)
        stop_loss_pct = sp.get('risk', {}).get('stop_loss_pct', 0.05)
        tp_mults = sp.get('risk', {}).get('tp_multipliers', {'third': 1.06, 'first': 1.08, 'trend': 1.10})

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
            max_buy_amount = account_info.get('initial_capital', 0) * pos_limit_pct
            target_amount = min(max_buy_amount, cash)
            buy_qty = int(target_amount // price // qty_unit * qty_unit)
            if buy_qty < 100:
                buy_qty = 0

            # 简化的近期高低判定（用MA区代替）
            # 横盘近似：均线粘合（MA20 与 MA10 接近），波动较小（用价格相对MA20偏离 < 3% 近似）
            consolidating = (abs(ma10 - ma20) / ma20 < pull_tol) and (abs(price - ma20) / ma20 < 3*pull_tol)

            # 第三类买点：突破横盘，趋势启动（最高优先级）或超跌反弹（RSI低位回升）
            trend_start = (ma5 > ma10 > ma20) and (price > ma5) and (macd > 0)
            oversold_rebound = (rsi <= rsi_buy_low) and (macd >= 0)
            third_buy = trend_start or oversold_rebound

            # 第一类买点：脱离后回归修正（回到均线带并企稳）
            first_buy = (ma5 >= ma10 >= ma20) and (abs(price - ma10) / ma10 < pull_tol)

            # 第二类买点：回调失败（难以有效跌破均线，RSI中性偏强）
            second_buy = (abs(price - ma10) / ma10 < pull_tol) and (rsi_neu_low <= rsi <= rsi_neu_high) and (ma5 >= ma10)

            break_trend = (price < ma20) and (macd < 0)
            rsi_cooling = (rsi > rsi_sell_high) and (price < ma5)

            pos = positions.get(stock)
            entry = pos['avg_price'] if pos else None
            stop_loss_hit = False
            if pos and entry:
                stop_loss_hit = (price <= entry * (1 - stop_loss_pct))

            # 决策
            if not has_pos:
                # 优先级顺序：第三 > 第一 > 第二
                if third_buy and buy_qty >= 100:
                    decisions[stock] = {
                        'signal': 'buy',
                        'quantity': buy_qty,
                        'tp': round(price * tp_mults.get('trend', 1.10), 2),
                        'sl': round(price * (1 - stop_loss_pct), 2),
                        'confidence': 0.8,
                        'reason': '第三类买点：趋势启动或RSI超跌反弹'
                    }
                elif first_buy and buy_qty >= 100:
                    decisions[stock] = {
                        'signal': 'buy',
                        'quantity': buy_qty,
                        'tp': round(price * tp_mults.get('first', 1.08), 2),
                        'sl': round(price * (1 - max(stop_loss_pct - 0.01, 0.03)), 2),
                        'confidence': 0.7,
                        'reason': '第一类买点：脱离后回归修正，靠近MA10企稳'
                    }
                elif second_buy and buy_qty >= 100:
                    decisions[stock] = {
                        'signal': 'buy',
                        'quantity': buy_qty,
                        'tp': round(price * tp_mults.get('third', 1.06), 2),
                        'sl': round(price * (1 - max(stop_loss_pct + 0.01, 0.04)), 2),
                        'confidence': 0.6,
                        'reason': '第二类买点：回调失败确认，趋势延续'
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
                        'reason': '第一类卖点：跌破MA20且MACD转负'
                    }
                elif rsi_cooling and sell_qty > 0:
                    decisions[stock] = {
                        'signal': 'sell',
                        'quantity': sell_qty,
                        'confidence': 0.7,
                        'reason': '第二类卖点：RSI>阈值后回落，价格跌破MA5'
                    }
                elif stop_loss_hit and sell_qty > 0:
                    decisions[stock] = {
                        'signal': 'sell',
                        'quantity': sell_qty,
                        'confidence': 0.9,
                        'reason': '第三类卖点：止损触发'
                    }
                else:
                    decisions[stock] = { 'signal': 'hold' }

        return decisions
    
    def _build_ashare_prompt(self, market_state: Dict, portfolio: Dict, account_info: Dict) -> str:
        """构建提示词：让LLM完全按PDF与帝论三类买卖点输出JSON决策"""
        sp = account_info.get('strategy_params', {})
        pull_tol = sp.get('ma', {}).get('pullback_tolerance', 0.01)
        rsi_buy_low = sp.get('rsi', {}).get('buy_low', 30)
        rsi_neu_low = sp.get('rsi', {}).get('neutral_low', 45)
        rsi_neu_high = sp.get('rsi', {}).get('neutral_high', 60)
        rsi_sell_high = sp.get('rsi', {}).get('sell_high', 70)
        pos_limit_pct = sp.get('risk', {}).get('position_limit_pct', 0.30)
        stop_loss_pct = sp.get('risk', {}).get('stop_loss_pct', 0.05)
        tp_mults = sp.get('risk', {}).get('tp_multipliers', {'third': 1.06, 'first': 1.08, 'trend': 1.10})

        lines = []
        lines.append("你是一位严格遵循两份PDF核心思想（简易交易系统+帝论三类买卖点）的中国A股专业交易员。")
        lines.append("请完全按照其中的规则、流程和风控要求进行交易决策，并只输出JSON。")

        lines.append("\n[市场数据与指标]")
        for code, d in market_state.items():
            name = d.get('name', code)
            price = d.get('price')
            chg = d.get('change_24h')
            ind = d.get('indicators', {})
            ma5 = ind.get('sma_5')
            ma10 = ind.get('sma_10')
            ma20 = ind.get('sma_20')
            rsi = ind.get('rsi_14')
            macd = ind.get('macd')
            lines.append(f"- {code}({name}): 价¥{price}, 涨跌{chg}%, MA5 {ma5}, MA10 {ma10}, MA20 {ma20}, RSI {rsi}, MACD {macd}")

        lines.append("\n[账户与持仓]")
        lines.append(f"初始资金: ¥{account_info.get('initial_capital')}, 总资产: ¥{portfolio.get('total_value')}, 现金: ¥{portfolio.get('cash')}, 总收益率: {account_info.get('total_return')}%")
        if portfolio.get('positions'):
            for pos in portfolio['positions']:
                cp = pos.get('current_price')
                pnl_pct = ((cp - pos['avg_price'])/pos['avg_price']*100) if cp and pos['avg_price'] else None
                lines.append(f"- {pos['coin']}: {int(pos['quantity'])}股 @¥{pos['avg_price']} (当前¥{cp}, {pnl_pct if pnl_pct is not None else 'NA'}% )")
        else:
            lines.append("- 无持仓")

        lines.append("\n[硬性约束]")
        lines.append("1) T+1：当日买入，次日才能卖出；避免当日反向操作。")
        lines.append("2) 涨跌停：普通±10%，ST±5%，避免触及涨跌停价位下单。")
        lines.append("3) 交易单位：买入须为100股整数倍；卖出末端不足100股可一次性清仓。")
        lines.append("4) 费用：买佣金约0.03%(最低5元)；卖佣金+印花税0.1%。")
        lines.append("5) 无杠杆：仅做多。")

        lines.append("\n[策略参数(供你严格参考)]")
        lines.append(f"pullback_tolerance: {pull_tol}")
        lines.append(f"RSI: buy_low {rsi_buy_low}, neutral [{rsi_neu_low},{rsi_neu_high}], sell_high {rsi_sell_high}")
        lines.append(f"risk: position_limit_pct {pos_limit_pct}, stop_loss_pct {stop_loss_pct}, tp_multipliers {tp_mults}")

        lines.append("\n[帝论三类买点与卖点要点——请据此判断]")
        lines.append("买点：")
        lines.append("- 第一类：趋势突破与启动（均线多头，关键位突破，MACD为正）")
        lines.append("- 第二类：上行趋势回踩确认（MA10/MA20附近企稳，RSI中性偏强）")
        lines.append("- 第三类：超跌反弹（RSI低位快速回升，伴随MACD改善）")
        lines.append("卖点：")
        lines.append("- 第一类：趋势破坏（跌破MA20且MACD转负）")
        lines.append("- 第二类：冲高回落（RSI>阈值后回落，价跌破MA5等迹象）")
        lines.append("- 第三类：止损退出（相对买入价跌破止损阈值）")

        lines.append("\n[风控与仓位]")
        lines.append("- 单票目标不超过初始资金的position_limit_pct；资金不足一手则hold。")
        lines.append("- 止损严格执行；止盈目标可参考tp_multipliers。")

        lines.append("\n[仅输出JSON，结构如下]")
        lines.append("{")
        lines.append("  \"股票代码\": { \"signal\": \"buy|sell|hold\", \"quantity\": 100, \"tp\": 15.50, \"sl\": 13.20, \"confidence\": 0.75, \"reason\": \"基于三类买/卖点的简短理由\" }")
        lines.append("}")
        lines.append("不要输出任何解释；仅返回JSON对象。若不满足买/卖条件则返回hold。")

        # 用户自定义提示词与策略文档参考
        custom_prompt = account_info.get('custom_prompt', '')
        docs = account_info.get('strategy_docs', [])
        if custom_prompt:
            lines.append("\n[用户自定义提示词——严格在上述约束下执行]")
            lines.append(custom_prompt)
        if docs:
            lines.append("\n[策略文档参考路径]")
            for p in docs:
                lines.append(f"- {p}")

        return "\n".join(lines)
    
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
        """解析LLM响应为结构化决策；容忍代码块包装并做字段校验"""
        s = response.strip()
        if '```' in s:
            # 尝试取最后一个代码块中的JSON
            parts = s.split('```')
            candidates = [p for p in parts if '{' in p and '}' in p]
            s = candidates[-1] if candidates else s
        # 取到JSON部分
        if '{' in s:
            s = s[s.find('{'):]
        if '}' in s:
            s = s[:s.rfind('}')+1]

        try:
            obj = json.loads(s)
        except Exception as e:
            raise Exception(f"LLM返回解析失败: {e}")

        clean = {}
        for code, d in obj.items():
            if not isinstance(d, dict):
                continue
            sig = str(d.get('signal', 'hold')).lower()
            qty = int(d.get('quantity', 0))
            tp = d.get('tp')
            sl = d.get('sl')
            reason = d.get('reason', '')
            conf = float(d.get('confidence', 0))
            clean[code] = {
                'signal': sig,
                'quantity': qty,
                'tp': tp,
                'sl': sl,
                'reason': reason,
                'confidence': conf
            }
        return clean
