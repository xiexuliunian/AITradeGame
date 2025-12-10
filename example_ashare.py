#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股交易系统使用示例
演示如何使用 AITradeGame A股版本进行模拟交易

使用方法：
1. 确保已安装依赖：pip install -r requirements.txt
2. 运行此脚本：python example_ashare.py
"""

import sys
import os
import traceback

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_market_data():
    """测试市场数据获取"""
    print("\n" + "="*60)
    print("测试 1: 市场数据获取")
    print("="*60)
    
    from market_data_ashare import AShareMarketDataFetcher
    
    fetcher = AShareMarketDataFetcher()
    
    # 测试股票列表
    stocks = ['600519', '000858', '601318']
    print(f"\n正在获取股票数据: {stocks}")
    
    # 获取当前价格
    prices = fetcher.get_current_prices(stocks)
    
    print("\n当前行情:")
    print("-" * 60)
    for stock, data in prices.items():
        print(f"{stock} ({data['name']})")
        print(f"  价格: ¥{data['price']:.2f}")
        print(f"  涨跌幅: {data['change_24h']:+.2f}%")
        print(f"  成交量: {data['volume']:,}")
        print()
    
    # 测试技术指标
    print("\n技术指标分析 (600519 贵州茅台):")
    print("-" * 60)
    indicators = fetcher.calculate_technical_indicators('600519')
    
    if indicators:
        print(f"当前价格: ¥{indicators['current_price']:.2f}")
        print(f"MA5:  ¥{indicators['sma_5']:.2f}")
        print(f"MA10: ¥{indicators['sma_10']:.2f}")
        print(f"MA20: ¥{indicators['sma_20']:.2f}")
        print(f"RSI:  {indicators['rsi_14']:.1f}")
        print(f"MACD: {indicators['macd']:.2f}")
        print(f"7日涨跌: {indicators['price_change_7d']:+.2f}%")
        print(f"30日涨跌: {indicators['price_change_30d']:+.2f}%")
    
    print("\n✓ 市场数据获取测试完成")

def test_trading_fees():
    """测试交易费用计算"""
    print("\n" + "="*60)
    print("测试 2: A股交易费用计算")
    print("="*60)
    
    # 模拟买入
    quantity = 100  # 100股 = 1手
    price = 1680.00  # 贵州茅台价格
    
    print(f"\n场景：买入 {quantity}股，价格 ¥{price:.2f}/股")
    print("-" * 60)
    
    trade_amount = quantity * price
    commission_rate = 0.0003
    commission = max(trade_amount * commission_rate, 5.0)
    total_cost = trade_amount + commission
    
    print(f"交易额: ¥{trade_amount:,.2f}")
    print(f"佣金 (0.03%, 最低5元): ¥{commission:.2f}")
    print(f"总成本: ¥{total_cost:,.2f}")
    
    # 模拟卖出
    print(f"\n场景：卖出 {quantity}股，价格 ¥{price*1.1:.2f}/股 (盈利10%)")
    print("-" * 60)
    
    sell_price = price * 1.1
    sell_amount = quantity * sell_price
    sell_commission = max(sell_amount * commission_rate, 5.0)
    stamp_duty = sell_amount * 0.001  # 印花税0.1%
    total_fee = sell_commission + stamp_duty
    
    gross_profit = (sell_price - price) * quantity
    net_profit = gross_profit - commission - total_fee
    
    print(f"卖出金额: ¥{sell_amount:,.2f}")
    print(f"佣金: ¥{sell_commission:.2f}")
    print(f"印花税 (0.1%): ¥{stamp_duty:.2f}")
    print(f"总费用: ¥{total_fee:.2f}")
    print(f"毛利润: ¥{gross_profit:,.2f}")
    print(f"净利润: ¥{net_profit:,.2f}")
    print(f"实际收益率: {(net_profit/total_cost)*100:.2f}%")
    
    print("\n✓ 交易费用计算测试完成")

def test_trading_rules():
    """演示A股交易规则"""
    print("\n" + "="*60)
    print("测试 3: A股交易规则说明")
    print("="*60)
    
    print("\n1. T+1 交易制度")
    print("-" * 60)
    print("   - 今天买入的股票，明天才能卖出")
    print("   - 今天卖出的股票，资金今天可用，明天可取")
    
    print("\n2. 涨跌停限制")
    print("-" * 60)
    print("   - 普通股票：±10%")
    print("   - ST股票：±5%")
    print("   - 新股上市首日：无涨跌停限制")
    
    print("\n3. 交易单位")
    print("-" * 60)
    print("   - 买入：必须是100股（1手）的整数倍")
    print("   - 卖出：可以不足100股时全部卖出")
    
    print("\n4. 交易时间")
    print("-" * 60)
    print("   - 上午：9:30 - 11:30")
    print("   - 下午：13:00 - 15:00")
    print("   - 周一至周五（法定节假日除外）")
    
    print("\n5. 费用标准")
    print("-" * 60)
    print("   买入：")
    print("     - 佣金：约0.03%（最低5元）")
    print("   卖出：")
    print("     - 佣金：约0.03%（最低5元）")
    print("     - 印花税：0.1%（国家规定）")
    
    print("\n✓ 交易规则说明完成")

def show_usage_guide():
    """显示使用指南"""
    print("\n" + "="*60)
    print("AITradeGame A股版本 - 使用指南")
    print("="*60)
    
    print("\n快速开始:")
    print("-" * 60)
    print("1. 安装依赖:")
    print("   pip install -r requirements.txt")
    print()
    print("2. 启动A股交易系统:")
    print("   python app_ashare.py")
    print()
    print("3. 访问Web界面:")
    print("   http://localhost:5000")
    print()
    print("4. 配置API提供方:")
    print("   - 点击 'API提供方' 按钮")
    print("   - 添加您的AI服务API密钥（如DeepSeek、OpenAI）")
    print()
    print("5. 添加交易模型:")
    print("   - 点击 '添加模型' 按钮")
    print("   - 选择提供方和模型")
    print("   - 设置初始资金（建议10万元起）")
    print()
    print("6. 查看交易结果:")
    print("   - 在主界面查看实时持仓和收益")
    print("   - 查看交易历史和AI决策过程")
    
    print("\n推荐配置:")
    print("-" * 60)
    print("- 初始资金: ¥100,000 - ¥500,000")
    print("- 交易频率: 5-10分钟")
    print("- AI模型: DeepSeek (性价比高，中文能力强)")
    print("- 股票池: 6只优质蓝筹股（已预配置）")
    
    print("\n注意事项:")
    print("-" * 60)
    print("- 这是模拟交易系统，不涉及真实资金")
    print("- 数据来源：akshare（未安装时使用模拟数据）")
    print("- AI决策仅供参考，不构成投资建议")
    print("- 实盘交易请谨慎决策，风险自负")
    
    print("\n更多信息:")
    print("-" * 60)
    print("- A股版本文档: README_ASHARE.md")
    print("- 原版文档: README.md (加密货币)")
    print("- 中文文档: README_ZH.md")

def main():
    """主函数"""
    print("\n" + "="*60)
    print("AITradeGame A股版本 - 演示脚本")
    print("="*60)
    
    try:
        # 运行所有测试
        test_market_data()
        test_trading_fees()
        test_trading_rules()
        show_usage_guide()
        
        print("\n" + "="*60)
        print("✅ 所有测试完成!")
        print("="*60)
        print("\n现在可以运行: python app_ashare.py 启动完整系统\n")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
