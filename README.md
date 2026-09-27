<div align="center">
<img src="src/shishi/desktop/assets/app-icon.png" width="112" alt="拾势图标" />

# 拾势 · A 股选股工具

基于同花顺 Financial API 的 macOS 桌面选股工具。

条件筛选 · 盘中快照 · 自选列表 · 历史走势

[下载 Mac 版](https://github.com/ives-cheung/shishi/releases/latest) · [申请 API Key](https://fuyao.aicubes.cn/admin/) · [构建说明](docs/BUILD.md)
</div>

拾势把 A 股行情、技术条件、基本面风险和自选列表放在一个桌面应用里。通过可调整的策略缩小观察范围，再查看候选股票的风险提示与历史走势。

这是基于 [HiThink-Tech/Financial-API](https://github.com/HiThink-Tech/Financial-API) 开发的独立项目，非同花顺官方客户端。**不提供自动交易、券商下单或收益保证；筛选结果不是买卖建议。**

## 功能

- **盘中 / 盘后筛选**：最新行情结合历史日线，支持价格、涨幅、成交额、20 日高点及累计涨幅等条件。
- **可调整策略**：直接输入阈值和评分权重，设置基本面软风险、缺失数据处理及可用权重归一化。
- **风险详情**：显示净利润、现金流、负债与估值检查发现的具体问题。
- **全市场搜索与自选**：按名称或代码搜索 A 股，一键加入自选；显示现价与涨跌幅，红涨绿跌。
- **历史走势**：自选股票支持近 3 个月、6 个月、1 年的前复权日线收盘价走势。
- **本地记录**：保存筛选结果、策略和自选，支持查看历史筛选记录。

## 安装与开始

目前发布 **Apple Silicon（M 系列芯片）、macOS 13 及以上**版本。无需安装 Python。Intel Mac 和 Windows 尚未构建与验证。

1. 从 [Releases](https://github.com/ives-cheung/shishi/releases/latest) 下载 ZIP，解压后把「拾势.app」拖进「应用程序」。
2. 到 [同花顺 API Key 管理页](https://fuyao.aicubes.cn/admin/)申请自己的 Key。
3. 首次启动填写 Key；之后可通过左下角钥匙图标修改。
4. 点击「搜索 A 股」搜索股票，或选择筛选模式后点击「运行筛选」。

安装包采用本地临时签名，**尚未经过 Apple Developer ID 签名和公证**。首次运行如被 macOS 拦截，确认下载来源后，可在「系统设置 → 隐私与安全性」允许打开。请勿全局关闭系统安全保护。

API 的可用权限、额度和行情更新速度取决于你自己的 Key 及上游服务；项目不附带共享 Key。

## 两种筛选模式

| 模式 | 运行时间 | 计算方式 |
| --- | --- | --- |
| 盘中 | 交易日 09:35–15:00，包含午休 | 当天行情快照 + 截至前一交易日的历史日线，每次重新取快照 |
| 盘后 | 交易日 16:00 后；休市日查看最近交易日 | 完整日线与行情快照校验，支持同日缓存 |

盘中成交额按已交易分钟数 / 240 进行线性进度比较，午休不累计时间。这是估算，**不是真实量比**，也未建模开收盘成交更集中的特征。开盘不足 5 分钟、行情非当天或延迟超过 10 个交易分钟时拒绝筛选；全市场分页行情跨越超过 5 分钟也会拒绝。

行情接口没有逐股交易时间，因此上述检查不能保证每只股票都是即时成交状态。结果会保留模式和时间信息；第一次全市场运行需获取较多历史及行业数据，可能较慢。没有符合条件的股票时允许空结果，不凑满名单。

盘中计算已通过自动化测试，但发布时尚未完成真实交易时段的端到端验证。

## 默认策略

| 类别 | 默认值 |
| --- | --- |
| 价格 | 优先 ≤30 元，不硬性排除更高价格 |
| 当日涨幅 | 2%–7% |
| 成交额 | 当日 ≥8000 万元，前 20 日平均 ≥3000 万元；盘中当天门槛随时间进度折算 |
| 放量 | 成交额倍数 ≥1.30；量比下限保存为 1.30，但当前接口缺失，按缺失策略处理 |
| 技术 | 距 60 日低点涨幅 ≤30%；相对前 20 日高点 0.95–1.05 |
| 连涨 | 5 日累计 ≤15%，20 日累计 ≤25% |
| 基本面 | 净利润同比下限 −40%，非金融业负债率上限 85%，PE 上限 150，PB 上限 15 |
| 风险处理 | 基本面软风险提示；缺失指标不直接淘汰；可用权重归一化到 100 分 |
| 输出 | 初筛最多 20 只，待复核候选最多 5 只 |

此外保留 ST/退市名称过滤、收盘或盘中价格位于当日振幅上方 40%、行业涨幅为正与行业前 30% 排名条件。亏损、负经营现金流和非正估值会提示风险。完整默认配置见 [config.json](src/shishi/config.json)。

评分权重为：20 日突破 20%、量比 20%、成交额 15%、当日涨幅 15%、换手率 10%、板块强度 10%、板块排名 10%。当前没有量比和换手率数据，通常可观察权重为 70%，界面显示覆盖率。分数用于同次候选横向比较，不是上涨概率，也不适合直接跨日比较。默认阈值未经过收益回测。

## 数据与隐私

- 数据来自同花顺 Financial API；目前不提供盘中分时线、tick 或 Level-2。
- 本项目不接入券商账户、不发送交易订单，也不上传你的自选列表到本项目服务器。
- API Key 以权限 `0600` 的本地文件保存，**不是加密存储**；应用请求直接发送到数据提供方。
- 安装版数据位于 `~/Library/Application Support/shishi/`，包含 `api-key.json`、`config.json`、`watchlist.json` 和 `results/`。
- 分享应用或提交 Issue 时，不要附带上述用户目录、Key 或未经检查的日志。

## 开发

需要 Python 3.11，桌面构建在目标架构的 Mac 上完成。

```bash
git clone https://github.com/ives-cheung/shishi.git
cd shishi
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/shishi/launcher.py
```

源码运行通过左下角钥匙按钮配置 Key，仅使用本应用自己的 Key 文件，不会自动借用其他工具的凭据。源码策略保存在 `src/shishi/config.json`，结果位于 `out/stock-screen/`。

```bash
python -m unittest discover -s src/shishi -p 'test_*.py'
python src/shishi/screen.py --mode intraday
python src/shishi/screen.py --mode eod --refresh
```

测试不需要真实 Key，不验证线上行情可用性。构建、目录结构与发布步骤见 [BUILD.md](docs/BUILD.md)。

## 致谢与许可

感谢 [HiThink-Tech/Financial-API](https://github.com/HiThink-Tech/Financial-API) 提供接口与 Python 客户端。仓库内 `vendor/` 保留了所使用客户端及凭据模块的源码和 MIT 许可证，来源版本见 [第三方说明](THIRD_PARTY_NOTICES.md)。

本项目原创代码采用 [MIT License](LICENSE)。Qt / PySide6 及其他依赖保留各自许可证；第三方依赖许可随应用分发。
