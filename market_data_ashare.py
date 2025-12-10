"""
Market data module - Chinese A-Share Stock Market
使用akshare库获取A股市场数据
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
        
        # 尝试导入akshare，如果失败则使用模拟数据
        self.use_mock = False
        try:
            import akshare as ak
            self.ak = ak
            print("[INFO] akshare library loaded successfully")
        except ImportError:
            print("[WARNING] akshare not installed, using mock data")
            print("[INFO] Install with: pip install akshare")
            self.use_mock = True
    
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
                    # 获取实时行情
                    # akshare获取实时行情数据
                    df = self.ak.stock_zh_a_spot_em()
                    
                    # 查找对应股票
                    stock_data = df[df['代码'] == stock_code]
                    
                    if not stock_data.empty:
                        row = stock_data.iloc[0]
                        prices[stock_code] = {
                            'price': float(row['最新价']),
                            'change_24h': float(row['涨跌幅']),
                            'name': row['名称'],
                            'volume': float(row.get('成交量', 0)),
                            'turnover': float(row.get('成交额', 0))
                        }
                    else:
                        print(f"[WARNING] Stock {stock_code} not found")
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
            # 获取个股详细数据
            df = self.ak.stock_zh_a_spot_em()
            stock_data = df[df['代码'] == stock_code]
            
            if stock_data.empty:
                return self._get_mock_market_data(stock_code)
            
            row = stock_data.iloc[0]
            
            return {
                'current_price': float(row['最新价']),
                'open_price': float(row.get('今开', 0)),
                'high_price': float(row.get('最高', 0)),
                'low_price': float(row.get('最低', 0)),
                'price_change': float(row.get('涨跌幅', 0)),
                'volume': float(row.get('成交量', 0)),
                'turnover': float(row.get('成交额', 0)),
                'amplitude': float(row.get('振幅', 0)),
                'pe_ratio': float(row.get('市盈率-动态', 0)),
                'pb_ratio': float(row.get('市净率', 0))
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
            # 计算日期范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            
            # 获取历史数据
            df = self.ak.stock_zh_a_hist(
                symbol=stock_code,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )
            
            if df.empty:
                return self._get_mock_historical_prices(stock_code, days)
            
            prices = []
            for _, row in df.iterrows():
                prices.append({
                    'timestamp': int(datetime.strptime(str(row['日期']), '%Y-%m-%d').timestamp() * 1000),
                    'price': float(row['收盘']),
                    'open': float(row['开盘']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'volume': float(row['成交量'])
                })
            
            return prices
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
