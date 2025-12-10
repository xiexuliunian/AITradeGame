"""
Market data module - Chinese A-Share Stock Market
使用baostock库获取A股市场数据
"""
import time
from typing import Dict, List
from datetime import datetime, timedelta

class AShareMarketDataFetcher:
    """Fetch real-time market data from Chinese A-Share market"""
    
    def __init__(self):
        # A股常用股票代码
        self.default_stocks = {
            '600519': '贵州茅台',  # Kweichow Moutai
            '000858': '五粮液',    # Wuliangye
            '601318': '中国平安',  # Ping An Insurance
            '600036': '招商银行',  # China Merchants Bank
            '000333': '美的集团',  # Midea Group
            '300750': '宁德时代'   # CATL
        }
        
        self._cache = {}
        self._cache_time = {}
        self._cache_duration = 5  # Cache for 5 seconds
        
        # 尝试导入baostock，如果失败则使用模拟数据
        self.use_mock = False
        self.bs = None
        self.bs_logged_in = False
        try:
            import baostock as bs
            self.bs = bs
            # 登录baostock系统
            lg = bs.login()
            if lg.error_code == '0':
                self.bs_logged_in = True
                print("[INFO] baostock library loaded and logged in successfully")
            else:
                print(f"[WARNING] baostock login failed: {lg.error_msg}")
                self.use_mock = True
        except ImportError:
            print("[WARNING] baostock not installed, using mock data")
            print("[INFO] Install with: pip install baostock")
            self.use_mock = True
    
    def __del__(self):
        """Logout from baostock when object is destroyed"""
        if self.bs and self.bs_logged_in:
            try:
                self.bs.logout()
            except:
                pass
    
    def _format_stock_code(self, stock_code: str) -> str:
        """Format stock code for baostock (需要添加交易所前缀)
        
        Args:
            stock_code: 6位股票代码，如 '600519'
            
        Returns:
            格式化的代码，如 'sh.600519' 或 'sz.000858'
        """
        if stock_code.startswith('6'):
            return f'sh.{stock_code}'  # 上海证券交易所
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return f'sz.{stock_code}'  # 深圳证券交易所
        else:
            return f'sh.{stock_code}'  # 默认上海
    
    def get_current_prices(self, stocks: List[str]) -> Dict[str, float]:
        """Get current prices from A-Share market
        
        Args:
            stocks: List of stock codes (e.g., ['600519', '000858'])
        
        Returns:
            Dict with stock prices and changes
        """
        # Check cache
        cache_key = 'prices_' + '_'.join(sorted(stocks))
        if cache_key in self._cache:
            if time.time() - self._cache_time[cache_key] < self._cache_duration:
                return self._cache[cache_key]
        
        if self.use_mock:
            return self._get_mock_prices(stocks)
        
        prices = {}
        
        try:
            for stock_code in stocks:
                try:
                    # 格式化股票代码
                    formatted_code = self._format_stock_code(stock_code)
                    
                    # 获取实时行情数据
                    rs = self.bs.query_latest_data(code=formatted_code)
                    
                    if rs.error_code == '0':
                        data_list = []
                        while (rs.error_code == '0') & rs.next():
                            data_list.append(rs.get_row_data())
                        
                        if data_list:
                            # baostock返回的数据是列表形式
                            row = data_list[0]
                            # 字段索引: 0-code, 1-name, 2-date, 3-time, 4-price, 5-pctChange等
                            prices[stock_code] = {
                                'price': float(row[4]) if row[4] else 0.0,  # 最新价
                                'change_24h': float(row[5]) if row[5] else 0.0,  # 涨跌幅
                                'name': self.default_stocks.get(stock_code, stock_code),
                                'volume': float(row[6]) if len(row) > 6 and row[6] else 0.0,  # 成交量
                                'turnover': float(row[7]) if len(row) > 7 and row[7] else 0.0  # 成交额
                            }
                        else:
                            print(f"[WARNING] Stock {stock_code} data empty")
                            prices[stock_code] = self._get_mock_price_single(stock_code)
                    else:
                        print(f"[WARNING] Failed to query {stock_code}: {rs.error_msg}")
                        prices[stock_code] = self._get_mock_price_single(stock_code)
                        
                except Exception as e:
                    print(f"[ERROR] Failed to fetch {stock_code}: {e}")
                    prices[stock_code] = self._get_mock_price_single(stock_code)
                    continue
            
            # Update cache
            self._cache[cache_key] = prices
            self._cache_time[cache_key] = time.time()
            
            return prices
            
        except Exception as e:
            print(f"[ERROR] A-Share market data fetch failed: {e}")
            return self._get_mock_prices(stocks)
    
    def _get_mock_prices(self, stocks: List[str]) -> Dict[str, float]:
        """Generate mock prices for testing"""
        import random
        
        mock_prices = {}
        base_prices = {
            '600519': 1680.0,  # 贵州茅台
            '000858': 180.0,   # 五粮液
            '601318': 45.0,    # 中国平安
            '600036': 38.0,    # 招商银行
            '000333': 65.0,    # 美的集团
            '300750': 220.0    # 宁德时代
        }
        
        for stock in stocks:
            base_price = base_prices.get(stock, 100.0)
            # 添加随机波动
            variation = random.uniform(-0.02, 0.02)
            current_price = base_price * (1 + variation)
            change_pct = random.uniform(-3.0, 3.0)
            
            mock_prices[stock] = {
                'price': current_price,
                'change_24h': change_pct,
                'name': self.default_stocks.get(stock, f'股票{stock}'),
                'volume': random.randint(100000, 10000000),
                'turnover': random.randint(10000000, 1000000000)
            }
        
        return mock_prices
    
    def _get_mock_price_single(self, stock_code: str) -> Dict:
        """Get mock price for a single stock"""
        return self._get_mock_prices([stock_code])[stock_code]
    
    def get_market_data(self, stock_code: str) -> Dict:
        """Get detailed market data for a stock"""
        if self.use_mock:
            return self._get_mock_market_data(stock_code)
        
        try:
            # 格式化股票代码
            formatted_code = self._format_stock_code(stock_code)
            
            # 获取实时行情数据
            rs = self.bs.query_latest_data(code=formatted_code)
            
            if rs.error_code != '0':
                return self._get_mock_market_data(stock_code)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return self._get_mock_market_data(stock_code)
            
            row = data_list[0]
            # baostock字段: code, name, date, time, price, pctChange, volume, amount, ...
            
            return {
                'current_price': float(row[4]) if row[4] else 0.0,
                'open_price': float(row[8]) if len(row) > 8 and row[8] else 0.0,
                'high_price': float(row[9]) if len(row) > 9 and row[9] else 0.0,
                'low_price': float(row[10]) if len(row) > 10 and row[10] else 0.0,
                'price_change': float(row[5]) if row[5] else 0.0,
                'volume': float(row[6]) if row[6] else 0.0,
                'turnover': float(row[7]) if row[7] else 0.0,
                'amplitude': 0.0,  # baostock可能不直接提供，需要计算
                'pe_ratio': 0.0,  # 需要单独查询
                'pb_ratio': 0.0   # 需要单独查询
            }
        except Exception as e:
            print(f"[ERROR] Failed to get market data for {stock_code}: {e}")
            return self._get_mock_market_data(stock_code)
    
    def _get_mock_market_data(self, stock_code: str) -> Dict:
        """Generate mock market data"""
        import random
        base_price = 100.0
        
        return {
            'current_price': base_price,
            'open_price': base_price * 0.99,
            'high_price': base_price * 1.02,
            'low_price': base_price * 0.98,
            'price_change': random.uniform(-3.0, 3.0),
            'volume': random.randint(100000, 10000000),
            'turnover': random.randint(10000000, 1000000000),
            'amplitude': random.uniform(0.5, 5.0),
            'pe_ratio': random.uniform(10.0, 50.0),
            'pb_ratio': random.uniform(1.0, 10.0)
        }
    
    def get_historical_prices(self, stock_code: str, days: int = 7) -> List[Dict]:
        """Get historical prices"""
        if self.use_mock:
            return self._get_mock_historical_prices(stock_code, days)
        
        try:
            # 格式化股票代码
            formatted_code = self._format_stock_code(stock_code)
            
            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')  # 多取一些以确保有足够数据
            
            # 获取历史K线数据
            rs = self.bs.query_history_k_data_plus(
                code=formatted_code,
                fields="date,code,open,high,low,close,volume,amount",
                start_date=start_date,
                end_date=end_date,
                frequency="d",  # 日线
                adjustflag="2"  # 前复权
            )
            
            if rs.error_code != '0':
                print(f"[ERROR] baostock query failed: {rs.error_msg}")
                return self._get_mock_historical_prices(stock_code, days)
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return self._get_mock_historical_prices(stock_code, days)
            
            prices = []
            for row in data_list[-days:]:  # 只取最近days天的数据
                try:
                    date_obj = datetime.strptime(row[0], '%Y-%m-%d')
                    prices.append({
                        'timestamp': int(date_obj.timestamp() * 1000),
                        'price': float(row[5]) if row[5] else 0.0,  # close价格
                        'open': float(row[2]) if row[2] else 0.0,
                        'high': float(row[3]) if row[3] else 0.0,
                        'low': float(row[4]) if row[4] else 0.0,
                        'volume': float(row[6]) if row[6] else 0.0
                    })
                except (ValueError, IndexError) as e:
                    print(f"[WARNING] Failed to parse row: {e}")
                    continue
            
            return prices if prices else self._get_mock_historical_prices(stock_code, days)
            
        except Exception as e:
            print(f"[ERROR] Failed to get historical prices for {stock_code}: {e}")
            return self._get_mock_historical_prices(stock_code, days)
    
    def _get_mock_historical_prices(self, stock_code: str, days: int) -> List[Dict]:
        """Generate mock historical prices"""
        import random
        
        base_price = 100.0
        prices = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=days-i-1)
            timestamp = int(date.timestamp() * 1000)
            
            # 随机游走
            variation = random.uniform(-0.03, 0.03)
            base_price = base_price * (1 + variation)
            
            prices.append({
                'timestamp': timestamp,
                'price': base_price,
                'open': base_price * 0.99,
                'high': base_price * 1.01,
                'low': base_price * 0.98,
                'volume': random.randint(100000, 1000000)
            })
        
        return prices
    
    def calculate_technical_indicators(self, stock_code: str) -> Dict:
        """Calculate technical indicators"""
        historical = self.get_historical_prices(stock_code, days=30)
        
        if not historical or len(historical) < 5:
            return {}
        
        prices = [p['price'] for p in historical]
        
        # Simple Moving Average
        sma_5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else prices[-1]
        sma_10 = sum(prices[-10:]) / 10 if len(prices) >= 10 else prices[-1]
        sma_20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else prices[-1]
        
        # Simple RSI calculation
        if len(prices) >= 14:
            changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            gains = [c if c > 0 else 0 for c in changes]
            losses = [-c if c < 0 else 0 for c in changes]
            
            avg_gain = sum(gains[-14:]) / 14 if gains else 0
            avg_loss = sum(losses[-14:]) / 14 if losses else 0
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 50  # 默认中性值
        
        # MACD简化计算
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        return {
            'sma_5': sma_5,
            'sma_10': sma_10,
            'sma_20': sma_20,
            'rsi_14': rsi,
            'macd': macd,
            'current_price': prices[-1],
            'price_change_7d': ((prices[-1] - prices[-7]) / prices[-7]) * 100 if len(prices) >= 7 and prices[-7] > 0 else 0,
            'price_change_30d': ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] > 0 else 0
        }
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # 初始SMA
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
