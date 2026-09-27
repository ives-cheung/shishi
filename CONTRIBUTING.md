# 参与贡献

请先阅读 README 和 docs/BUILD.md。Bug 报告包含系统、版本、复现步骤及脱敏截图。修改筛选计算时补充有意义的测试，并说明数据口径；不要以合成行情冒充真实验证。

提交前运行 `python -m unittest discover -s src/shishi -p 'test_*.py'`。不要提交 API Key、缓存、用户自选、构建产物或真实私人配置。数据源能力不足时应明确显示缺失，不用其他指标悄悄替代。
