# Marketing ROI Analysis

AI 驱动的营销投放分析与预算决策项目。项目目标是从历史 campaign 数据出发，解释渠道贡献、计算投放效率指标、预测未来效果、生成预算建议，并通过实验验证建议是否有效。

## 内容导航

| 目标 | 入口 |
| --- | --- |
| 查看模型代码和运行方式 | [模块索引](modules/README.md) |
| 查看产品说明和研究资料 | [文档索引](docs/README.md) |
| 查看 Product Brief、PRD 与设计决策 | [设计产物索引](design-artifacts/README.md) |
| 查看已执行规格和延期事项 | [BMad 产物索引](_bmad-output/README.md) |
| 查看连续工作记录 | [工作日志](log.md) |

## 决策链路

```text
历史 campaign 数据
   ↓
基础指标计算 + MTA 归因
   ↓
渠道贡献、归因收入、ROI / ROAS / CPA 等诊断结果
   ↓
效果预测
   ↓
预算优化
   ↓
A/B 测试或准实验验证
   ↓
下一轮 campaign 决策
```

ROI、ROAS 和 CPA 是由花费、收入、转化及归因结果计算得到的派生指标，不是独立模型。

## 当前建设状态

| 能力 | 类型 | 状态 | 位置 |
| --- | --- | --- | --- |
| MTA 归因 | 模型 | 已有初步实现 | [`modules/mta/`](modules/mta/) |
| AMC MTA 归因 | 数据源专用模型流程 | 已有初步实现 | [`modules/amc_mta/`](modules/amc_mta/) |
| ROI / ROAS / CPA | 派生指标 | 已在通用 MTA 和 AMC MTA 流程中计算 | [`modules/amc_mta/`](modules/amc_mta/) |
| 效果预测 | 模型 | 尚未搭建 | — |
| 预算优化 | 模型 | 尚未搭建 | — |
| 实验验证 | 验证方法 | 研究阶段 | [`docs/research/ab-testing/`](docs/research/ab-testing/) |
| AI 问答 | 交互能力 | 尚未搭建 | — |

未开发的模型不会预先创建空目录；开始实现时再在 `modules/` 下建立对应模块。

## 项目结构

```text
.
├── README.md                 # 项目总览
├── log.md                    # 连续工作日志
├── data/                     # 跨模块共享数据规则
├── docs/
│   ├── product/              # 项目级产品和模型关系说明
│   └── research/             # 论文、调研资料和外部参考数据
├── modules/
│   ├── mta/                  # 通用 MTA 模型的代码、数据、输出和文档
│   └── amc_mta/              # 基于 AMC aggregated path report 的 MTA 流程
├── design-artifacts/         # Product Brief、PRD 和产品决策记录
├── .agents/                  # Agent 技能
├── _bmad/                    # BMad 工作流配置
└── _bmad-output/             # 已执行规格和实现记录
```

管理原则：

- 模块专用代码、数据和输出保存在对应的 `modules/<module>/` 中。
- 多个模型共享的数据以后统一放到顶层 `data/`。
- 外部论文、调研报告和 Amazon API 参考数据放在 `docs/research/`。
- 模型运行生成的可再生结果放在模块自己的 `outputs/`。
- ROI 等确定性计算指标留在使用它们的分析流程中，不建立独立模型目录。
- `.agents/` 与 `_bmad/` 是已安装工具资产，不作为业务内容整理或移动。
- `_bmad-output/` 保存有追溯价值的规格和实现记录，可以纳入版本管理。

## MTA 模块

目前的可运行实现位于 [`modules/mta/`](modules/mta/)，包含：

- Markov Chain Attribution
- Shapley Value Attribution
- 渠道贡献、归因转化和归因收入计算
- ROI、ROAS、CPA 指标计算
- Bootstrap 稳定性分析与 SVG 图表

运行环境需要 Python 3.10 或更高版本；当前实现只使用 Python 标准库。

运行完整流程：

```bash
python3 modules/mta/run_pipeline.py
```

详细用法见：

- [MTA 模块说明](modules/mta/README.md)
- [MTA 使用说明](modules/mta/docs/usage.md)
- [MTA 数据要求](modules/mta/docs/mta-data-requirements.md)

## AMC MTA 模块

AMC 专用流程位于 [`modules/amc_mta/`](modules/amc_mta/)。它从概念事件构建 AMC 风格匿名聚合路径，运行 Markov 和 Shapley，并关联 Amazon Ads 成本计算 ROI、ROAS 和 CPA。概念事件仅用于本地演示，不代表 AMC 可以导出用户级明细。

运行：

```bash
python3 modules/amc_mta/run_pipeline.py
```

详细用法见：

- [AMC MTA 模块说明](modules/amc_mta/README.md)
- [AMC MTA 数据要求](modules/amc_mta/docs/amc-data-requirements.md)
- [AMC 背景与数据流](docs/research/amazon/amc/README.md)
- [AMC MTA 项目介绍](docs/product/amc-mta/project-introduction.md)

## 项目文档

- [文档索引](docs/README.md)
- [模块索引](modules/README.md)
- [模型功能与关系说明](docs/product/model-relationship-guide.md)
- [Product Brief](design-artifacts/A-Product-Brief/product-brief.md)
- [PRD](design-artifacts/A-Product-Brief/prd.md)
- [模型与技术补充](design-artifacts/A-Product-Brief/addendum.md)
- [工作日志](log.md)

## 研究资料

```text
docs/research/
├── amazon/                   # Amazon Ads API 数据与调研报告
├── ab-testing/               # A/B 测试论文与阅读顺序
├── mta/                      # MTA 论文与学习笔记
├── machine-learning/         # 机器学习资料
├── ontology/                 # 本体论研究
└── industry/                 # 跨行业营销 AI 资料
```

`docs/research/amazon/research/` 中的 JSON 属于外部 API 参考数据，不是 MTA 模块的运行输入。

## 工作约定

- 原始或外部资料避免重复保存。
- 新增研究资料时，放入对应主题目录，并在主题 README 中补充来源和用途说明。
- 新模型达到可开发状态后，再创建独立模块及模块级 README。
- 运行输出必须能够由代码和输入数据重新生成。
- 不提交密钥、Token、个人身份信息或本地环境文件。
- 新增、重命名或移动主要目录后，同步更新根 README 和对应分区 README。
