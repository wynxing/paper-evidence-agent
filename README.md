# Paper Evidence Agent

本项目旨在核对论文中的论断与所引文献之间的证据关系。目标是让 paper agent 提供可定位的原文依据。系统应标明「证据不足」或「无法核验来源」。paper agent 的标签不自动等于事实正确。

本仓库按[传智杯「AI赋能·智能测试创新挑战赛」](https://www.boxuegu.com/matchTrack/detail/?id=10041)的路径一施工。参赛实现只有 paper agent。路径一的评审由仓库外的成熟 agent 完成，例如 Claude、Cursor；本仓库不实现第二名评审。路径二的独立测试平台不在范围内。赛题举例中的校园助手、法律文书等不改变本场景。

协作规范见 [AGENTS.md](AGENTS.md)。参赛首版按下面的顺序阅读。结果标签、任务状态、错误码和诊断包字段只在术语表定义。

1. [术语表](docs/glossary.md)
2. [产品需求](docs/prd.md)
3. [架构设计](docs/architecture.md)
4. [测试方案](docs/test-plan.md)
5. [技术选型](docs/tech-stack.md)

模型标准入口为本机 LiteLLM Proxy，paper agent 在预算内执行查询生成、检索、判断与必要的补读/修复；日常核验与固定配置评测分别定义恢复策略。首版接受中英文论断与英文 PMC 正文，包含任务内修改澄清、取消与执行时限。保留本地轨迹，可选授权后导出 Langfuse，观测故障不阻断核验。首版测试包含人工核对原文的小规模语义验收，单列冲突类指标；摘录存在不等于判断正确。

决策沿革见 [决策记录](docs/decisions.md)，检查结果及未覆盖范围见 [验证记录](docs/verification.md)。本地运行 `python scripts/check_docs.py` 检查文档，检查器回归运行 `python -m unittest discover -s scripts/tests`；CI 运行同样检查，不代表应用或模型测试通过。

这些文档描述拟实施方案，不代表系统已开发或实验已完成。正文用「规则 / 假设 / 排除 / 待决」区分已决定的行为、研究命题、范围之外和尚未选择的点。四种标记的说明见 [术语表](docs/glossary.md)。

[研究评测](docs/evaluation.md)不进入参赛首版施工。运行时代码不得依赖其中的数据集。
