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
        """做出交易决策"""
        prompt = self._build_ashare_prompt(market_state, portfolio, account_info)
        
        response = self._call_llm(prompt)
        
        decisions = self._parse_response(response)
        
        return decisions
    
    def _build_ashare_prompt(self, market_state: Dict, portfolio: Dict, 
                            account_info: Dict) -> str:
        """构建A股市场交易提示词"""
        prompt = f"""你是一位专业的中国A股交易员。请分析市场并做出交易决策。

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
A股交易规则：
1. T+1交易制度：当天买入的股票，第二天才能卖出
2. 涨跌停限制：普通股票±10%，ST股票±5%
3. 交易单位：买入必须是100股（1手）的整数倍
4. 费用：
   - 买入：佣金（约0.03%，最低5元）
   - 卖出：佣金（约0.03%，最低5元）+ 印花税（0.1%）
5. 无杠杆：A股不支持融资融券保证金交易（本系统）
6. 交易时间：周一至周五 9:30-11:30, 13:00-15:00（节假日除外）

投资策略建议：
1. 风险控制：
   - 单只股票仓位不超过总资金的20-30%
   - 保持一定现金储备（至少10-20%）
   - 及时止损，控制单笔亏损在2-5%以内
   
2. 选股要点：
   - 关注基本面：市盈率、市净率、ROE等
   - 技术面分析：均线、MACD、RSI等指标
   - 成交量：放量上涨、缩量下跌
   - 行业热点和政策导向
   
3. 买卖时机：
   - 买入：技术指标向好，突破关键阻力位
   - 卖出：达到止盈目标，或技术指标转弱
   - RSI > 70 超买，考虑卖出
   - RSI < 30 超卖，考虑买入

输出格式（仅JSON）：
```json
{
  "股票代码": {
    "signal": "buy|sell|hold",
    "quantity": 100,
    "profit_target": 15.50,
    "stop_loss": 13.20,
    "confidence": 0.75,
    "justification": "简短理由"
  }
}
```

注意：
- quantity 必须是100的整数倍
- signal只能是：buy（买入）、sell（卖出）、hold（持有）
- 已有持仓的可以sell，没有持仓的可以buy
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
