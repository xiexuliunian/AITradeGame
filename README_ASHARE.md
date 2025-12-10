# AITradeGame - A股版本

[English](README.md) | [中文](README_ZH.md) | [A股版本](README_ASHARE.md)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

AITradeGame A股版本是一个专为中国A股市场设计的AI交易模拟平台，完全适配A股市场规则和交易特性。

## 主要特性

### A股市场专属功能

- **完整的A股交易规则**
  - T+1 交易制度：当日买入股票次日才能卖出
  - 涨跌停限制：普通股票±10%，ST股票±5%
  - 交易单位：买入必须是100股（1手）的整数倍
  - 真实费用计算：佣金（双向）+ 印花税（仅卖出）
  - 无杠杆交易：符合A股市场实际情况

- **实时A股行情数据**
  - 使用 akshare 库获取真实A股数据
  - 支持实时行情、历史K线数据
  - 技术指标计算：MA、RSI、MACD等
  - 基本面数据：市盈率、市净率、成交量等

- **中文AI交易策略**
  - 专为A股市场优化的AI提示词
  - 理解中国股市特点和政策导向
  - 支持各类大语言模型（OpenAI、DeepSeek、Claude等）
  - 中文交易决策和分析报告

### 默认股票池

系统预设6只优质A股标的：

| 股票代码 | 股票名称 | 行业 |
|---------|---------|------|
| 600519  | 贵州茅台 | 白酒 |
| 000858  | 五粮液   | 白酒 |
| 601318  | 中国平安 | 保险 |
| 600036  | 招商银行 | 银行 |
| 000333  | 美的集团 | 家电 |
| 300750  | 宁德时代 | 新能源 |

## 快速开始

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/xiexuliunian/AITradeGame.git
cd AITradeGame

# 安装依赖
pip install -r requirements.txt
```

### 运行A股版本

```bash
# 启动A股交易系统
python app_ashare.py
```

程序会自动：
1. 初始化数据库（创建 `AITradeGame_AShare.db`）
2. 启动Web服务器（http://localhost:5000）
3. 打开浏览器界面
4. 开始自动交易循环

### Docker 部署

创建 `docker-compose-ashare.yml`:

```yaml
version: '3.8'
services:
  aitradegame-ashare:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    command: python app_ashare.py
    environment:
      - PYTHONUNBUFFERED=1
```

运行:
```bash
docker-compose -f docker-compose-ashare.yml up -d
```

## 配置说明

### 1. 添加API提供方

首先配置AI服务提供方：
1. 点击"API提供方"按钮
2. 输入提供方名称（如：DeepSeek、OpenAI）
3. 输入API地址和密钥
4. 可选：自动获取可用模型列表
5. 保存配置

推荐的中文AI模型：
- **DeepSeek**: deepseek-chat（性价比高，中文能力强）
- **OpenAI**: gpt-4, gpt-3.5-turbo
- **Claude**: claude-3-opus, claude-3-sonnet

### 2. 添加交易模型

配置AI交易模型：
1. 点击"添加模型"按钮
2. 选择已配置的API提供方
3. 选择具体模型
4. 设置模型名称和初始资金（建议10万元起）
5. 提交后自动开始交易

### 3. 系统设置

可配置参数：
- **交易频率**：5-60分钟（A股推荐5-10分钟）
- **佣金费率**：默认0.03%（可根据券商调整）
- **印花税率**：0.1%（国家规定，仅卖出收取）

## A股交易规则说明

### 费用计算

**买入时**：
```
成本 = 股数 × 价格 + 佣金
佣金 = max(股数 × 价格 × 0.0003, 5元)
```

**卖出时**：
```
收入 = 股数 × 价格 - 佣金 - 印花税
佣金 = max(股数 × 价格 × 0.0003, 5元)
印花税 = 股数 × 价格 × 0.001
```

### 交易限制

1. **最小交易单位**：100股（1手）
2. **涨跌停**：普通股票±10%，ST股票±5%
3. **T+1制度**：当日买入不可卖出
4. **交易时间**：
   - 上午：9:30 - 11:30
   - 下午：13:00 - 15:00
   - 周一至周五（节假日除外）

## 数据来源

- **行情数据**: [akshare](https://github.com/akfamily/akshare) - 开源金融数据接口
- **技术指标**: 本地计算（MA、RSI、MACD等）
- **基本面数据**: akshare提供的上市公司数据

## 使用建议

### 风险控制

1. **仓位管理**
   - 单只股票仓位不超过30%
   - 保持至少20%现金储备
   - 分散投资，不要集中持仓

2. **止损止盈**
   - 设置明确的止损点（如-5%）
   - 设置合理的止盈点（如+15%）
   - 及时锁定利润

3. **风险提示**
   - 本系统仅用于模拟交易和策略测试
   - 不构成任何投资建议
   - 实盘交易请谨慎决策

### 策略优化

AI会根据以下因素做出决策：
- 技术指标（均线、RSI、MACD）
- 价格走势和成交量
- 当前持仓和资金状况
- 风险收益比

您可以通过以下方式优化：
- 调整初始资金规模
- 选择不同的AI模型
- 修改交易频率
- 自定义股票池（修改代码）

## 技术架构

```
├── app_ashare.py              # A股版本主程序
├── market_data_ashare.py      # A股市场数据获取
├── trading_engine_ashare.py   # A股交易引擎
├── ai_trader_ashare.py        # A股AI交易员
├── database.py                # 数据库管理
└── requirements.txt           # 依赖包（包含akshare）
```

## 开发和贡献

### 自定义股票池

编辑 `trading_engine_ashare.py`:
```python
self.stocks = ['600519', '000858', ...]  # 修改为您想要的股票代码
```

### 调整交易策略

编辑 `ai_trader_ashare.py` 中的提示词模板，可以：
- 修改风险偏好
- 调整仓位控制规则
- 自定义技术指标权重
- 添加行业和政策因素

### 数据源切换

如果akshare不可用，系统会自动切换到模拟数据模式：
- 基于合理的价格波动生成模拟数据
- 保持技术指标计算的准确性
- 适合离线测试和开发

## 常见问题

**Q: akshare安装失败怎么办？**
```bash
# 使用清华镜像源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple akshare
```

**Q: 如何添加更多股票？**

修改 `trading_engine_ashare.py` 和 `app_ashare.py` 中的 `stocks` 列表。

**Q: 可以用于实盘交易吗？**

本系统仅用于模拟和学习，不建议直接用于实盘。实盘交易请：
1. 充分测试策略
2. 咨询专业投资顾问
3. 了解相关风险

**Q: 支持哪些AI模型？**

支持所有OpenAI兼容的API：
- OpenAI (GPT-4, GPT-3.5)
- DeepSeek (推荐，中文能力强)
- Claude (通过OpenRouter)
- 其他兼容OpenAI格式的服务

## 免责声明

1. 本软件仅用于教育和研究目的
2. 模拟交易结果不代表实际交易收益
3. 使用AI进行投资决策存在风险
4. 不构成任何投资建议
5. 实际投资请谨慎决策，风险自负

## 相关链接

- 原版（加密货币）: https://github.com/chadyi/AITradeGame
- 本仓库: https://github.com/xiexuliunian/AITradeGame
- akshare文档: https://akshare.akfamily.xyz/

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 致谢

- 原版AITradeGame作者
- akshare开源项目
- 所有贡献者
