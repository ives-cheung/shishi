# 构建与发布

## 环境

- Apple Silicon Mac、macOS 13 或更新版本
- Python 3.11；发布构建已在 Python 3.11.12 上验证
- PyInstaller 与依赖版本见根目录 requirements-build.txt / requirements.txt

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python -m unittest discover -s src/shishi -p 'test_*.py'
python src/shishi/packaging/build.py
```

构建资源使用白名单，只包含代码、默认策略、图标和第三方许可证，不复制用户目录、凭据、自选、行情缓存或筛选结果。依赖从当前构建虚拟环境收集；推荐使用干净环境。改变依赖版本时也应同步第三方许可证。

输出为 `dist/shishi-portable/拾势.app`。默认临时签名，不含 Developer ID 公证。不要把 arm64 包标为通用或 Intel 版本；其他平台需单独构建验证。

## 目录

- `src/shishi/desktop/`：PySide6 界面、搜索、自选和行情子进程
- `src/shishi/screen.py`：筛选流程与结果输出
- `src/shishi/intraday.py`：交易时段、快照时效和盘中计算
- `src/shishi/runtime.py`：资源位置、用户数据、凭据与子进程入口
- `src/shishi/api_client.py`：本应用专用凭据适配
- `src/shishi/launcher.py`：源码和冻结应用的统一入口
- `src/shishi/packaging/`：构建脚本和第三方许可证
- `vendor/`：上游客户端最小依赖源码

## 发布检查

1. 在空白用户目录测试首次启动，确认提示填写自己的 Key。
2. 无 Key 时验证搜索、行情、筛选不会借用环境变量或其他客户端的凭据。
3. 使用临时用户目录验证合法 Key 的真实网络调用，测试后删除临时目录。
4. 检查 bundle 不含 `api-key.json`、`credentials.env`、`watchlist.json`、`result.json`。
5. `codesign --verify --deep --strict dist/shishi-portable/拾势.app`。
6. 使用 `ditto -c -k --sequesterRsrc --keepParent` 打 ZIP，附 SHA-256，上传 GitHub Release；不要提交二进制到 Git 历史。

## 测试范围

单元与流程测试覆盖交易时段、午休、日期与时间失效、盘中/历史数据边界、进度折算、缺失数据及软风险评分。测试中的虚构行情只作为测试夹具，不进入应用结果。

GUI 和独立包在本机 Apple Silicon macOS 环境测试；没有跨所有 macOS 版本验证，盘中真实交易时段的端到端验证尚未完成。
