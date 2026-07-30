# Marketing ROI Analysis

本工作区包含两项边界清晰的业务模块、一套本地 Agent/BMad 开发工具以及完整的研究和
历史追溯资料：[`modules/amc_mta/`](modules/amc_mta/) 提供五段触点归因证据，
[`modules/mta_strategy_recommender/`](modules/mta_strategy_recommender/) 目前以
Campaign Group 为顶层，提供与 AMC 触点、实体和预算逐条对齐的初始策略数据契约、样例
和只读校验；自动生成推荐的 adapter/generator 是后续阶段。

AMC MTA 使用五段互动键区分广告产品、形式、位置、创意和曝光/点击，分别运行 Markov 与 Path-level Shapley。策略初始化器采用 `Campaign Group → Campaign → Ad Group → Keyword/SKU` 业务树；`ad_product` 只是 Campaign 的固有字段。两者都不是生产级因果归因或自动预算优化系统。

## 从这里开始

| 目标 | 入口 |
| --- | --- |
| 查看全工作区盘点、评价与风险 | [工作区总览](docs/project-overview.md) |
| 理解所有目录与阅读顺序 | [全工作区文档总索引](docs/index.md) |
| 查看项目文档入口说明 | [文档索引说明](docs/README.md) |
| 管理新增、移动和归档文件 | [工作区文件位置管理](docs/workspace-file-management.md) |
| 查看声明范围内文件的大小、权限和哈希 | [工作区文件清单](docs/workspace-file-inventory.json)（排除 Git、`log.md`、ignored 个人覆盖及清单自身） |
| 运行 AMC MTA 归因 | [AMC MTA 模块说明](modules/amc_mta/README.md) |
| 验证初始策略层级样例 | [策略初始化器说明](modules/mta_strategy_recommender/README.md) |
| 查看业务模块目录约定 | [模块索引](modules/README.md) |
| 查看架构与数据流 | [AMC MTA 架构](docs/amc_mta/amc-mta-architecture.md) |
| 查看成熟度、风险与路线 | [AMC MTA 能力评价](docs/amc_mta/amc-mta-capability-assessment.md) |
| 查看输入、路径和指标契约 | [AMC MTA 数据契约](modules/amc_mta/docs/amc-data-requirements.md) |
| 查看双模型治理与证据阻断 | [模型比较治理规范](modules/amc_mta/docs/model-comparison-governance.md) |
| 判断单触点归因是否可靠 | [触点可靠性指南](modules/amc_mta/docs/touchpoint-reliability-guide.md) |
| 查看外部研究资料 | [研究资料分级索引](docs/research/README.md) |
| 查看历史产品愿景 | [历史设计产物](design-artifacts/README.md) |
| 查看规格与实现记录 | [BMad 产物索引](_bmad-output/README.md) |

## 当前能力

```text
合成用户事件主表（仅本地演示）
          ↓
匿名概念事件 + Ads 日报 + 触点实体聚合
          ↓
AMC 风格匿名聚合五段路径
          ↓
Markov + Path-level Shapley
          ↓
五段归因结果 + Amazon Ads 成本
          ↓
双模型差异、支持度和治理状态

独立策略契约样例：Campaign Group
          ↓
Campaign → 推荐 Ad Group → Keyword/SKU
```

- 一份模拟事实源及四类派生数据：匿名概念事件、聚合路径、Amazon Ads 日报和触点实体聚合。
- 五段键：`AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`。
- 三个独立 outcome：购买用户、购买次数和收入。
- 五份正式输出：两份 18 列模型结果，以及 14/13/15 列的触点比较、整体摘要和推荐结果。
- 当前样例有 17 个五段触点；推荐文件包含 51 条触点/outcome 记录。
- 三份双模型产物直接给出三项可靠性标准；当前90天样例为 `51 RELIABLE / 0 UNRELIABLE`。
- 推荐结果还按可靠性给出最终值：可靠时使用 Markov 正式 share，不可靠时使用
  Markov/Shapley share 的升序闭区间；不输出自动化许可字段。
- 独立策略样例用两个 JSON 输入表达一个 Campaign Group、四个 Campaign、冻结候选池和
  AMC SHA/窗口；六个推荐 Ad Group 按六个入选触点归一化，明确披露 `17 → 6`，仍是测试
  夹具，不代表生成器已经实现，也不宣称最优。

## 快速验证

运行环境需要 Python 3.10 或更高版本；当前实现只使用 Python 标准库。

```bash
python3 -B modules/amc_mta/run_pipeline.py
python3 modules/amc_mta/scripts/validate_data_alignment.py
python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'
python3 modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python3 -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'
```

预期结果：

- 流水线从 Ads 输入自动识别日期窗口，重建匿名聚合路径并发布五份契约输出；
- 17 个 AMC 与 Amazon Ads 五段触点、90 天覆盖和账户/币种范围严格对齐；
- 107 项 AMC MTA 测试和 39 项策略对齐测试通过；
- 当前 51 条推荐记录均为 `RELIABLE`。

## 项目结构

```text
.
├── README.md
├── log.md
├── docs/
│   ├── index.md
│   ├── amc_mta/               # AMC MTA 工作区文档
│   ├── product/              # 当前项目介绍
│   └── research/             # 外部研究原件和相关性索引
├── modules/
│   ├── amc_mta/              # 五段触点归因实现
│   └── mta_strategy_recommender/ # Campaign Group 初始策略模块
├── design-artifacts/         # 历史 Product Brief、PRD 与决策记录
├── .agents/                  # 已安装 Agent 技能
├── _bmad/                    # BMad 工作流配置
└── _bmad-output/             # 规格、评审状态和实现记录
```

`.agents` 和 `_bmad` 是安装型开发工具，不参与 AMC MTA 运行；`design-artifacts`
和 `_bmad-output` 用于历史追溯；`docs/research` 的外部原件不是模型输入。

## 明确边界

- 概念事件样例只用于演示本地路径算法，不代表 AMC 可以导出用户级明细。
- Markov 是治理上的正式展示口径，Shapley 是模型敏感性参照；两者不取平均。
- 当前结果是归因诊断，不是广告因果增量证据。
- 当前没有滚动窗口、重采样稳定性、生产隐私执行、自动预算或投放执行能力。
- 策略模块只交付可解释初始点；长期优化由下游专业流程负责。
- Product Brief、PRD、预测、优化、实验和 AI 问答内容保留为历史愿景，不代表当前交付范围。
- 外部 PDF、DOCX、JSON 和研究笔记保留在 `docs/research/`，不作为模块运行输入。
