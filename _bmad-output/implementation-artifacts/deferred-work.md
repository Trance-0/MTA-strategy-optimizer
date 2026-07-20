# Deferred Work

以下问题由 `AMC MTA 增加曝光与点击互动粒度` 的独立审查发现，但属于既有实现或需要单独设计决策，不在本次变更范围内。

- AMC 事件当前只按 `journey_id` 分组；应评估按 marketplace、advertiser、journey 联合隔离，避免跨范围复用 ID 时串联路径。
- 无时区的事件时间当前按 UTC 解释；应决定强制 `Z/offset`，还是增加明确的输入时区配置。
- Amazon Ads 输入应补充完整 schema 校验，并决定是否拒绝同一基础触点、同一天的重复行，避免缺列补零或重复累计成本。
- AMC 路径报告没有 currency，无法程序化验证收入币种与 Ads 成本币种一致；需要扩展契约或在上游固定币种。
- 计数字段经 `float` 解析，在超过 `2**53` 时可能丢失整数精度；应改为十进制整数解析，金额评估使用 `Decimal`。
- `users=0` 的聚合行可能导致 Markov 与 Shapley 的零权重触点集合不一致；应决定拒绝零用户行还是输出显式零归因行。
- 独立运行 `run_amc_attribution.py` 只有单文件原子写入，四文件写入中途失败可能形成混合版本；可复用整组发布机制。
- 多个 pipeline 并发发布同一输出目录时缺少进程锁或版本目录切换，需要单独设计并发发布策略。
- CSV 读取器应拒绝重复规范化表头，并用明确 schema 识别 Amazon Ads 的说明行，而不是仅检查首单元格文本。
- Markov removal effect 当前采用“遇到被移除触点后转 Null 并截断”且负 effect 截零；应单独评审模型定义、负贡献语义和可手算基准案例。

## 全量评估 AMC MTA 双模型输出审查

- 当前整组发布可在失败时回滚，但多个并发读取者仍可能在连续文件替换之间观察到瞬时的新旧混合；如需强一致读取，应另行设计版本目录加原子 manifest/指针切换。

## 工作区整理审查发现的既有 AMC 问题

- `modules/amc_mta/docs/usage.md` 与触点可靠性指南中的“正式 Markov”措辞可能被误读为已经通过证据治理；应与 `EVIDENCE_UNVERIFIED`、空 `decision_value` 和 `automation_allowed=false` 的阻断语义统一。
- 触点可靠性等级未覆盖所有支持度、稳定性、差距等级和 outcome spread 组合；应补全确定性决策表、`stability_level` 通过条件及缺失值处理。
- `difference_level` 的组合门槛、相对差公式、零均值规则以及“重要贡献来源”的判据尚未完整定义，需与代码中的唯一阈值事实源对齐。
- 四份既有 AMC 输出 CSV 含尾随空格，导致完整 `git diff --check` 和严格表头读取失败；本次整理按保护边界未重写输出，应另行决定恢复规范生成格式。
