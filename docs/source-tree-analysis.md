# 工作区目录结构分析

## 总体结构

```text
marketing-roi-analysis/
├── README.md                         # 工作区与业务入口
├── log.md                            # 人工工作记录
├── .gitignore                        # 缓存、秘密和生成输出规则
├── .markdownlint.json                # Markdown lint 例外
├── modules/
│   ├── amc_mta/                      # 五段触点归因实现
│   └── mta_strategy_recommender/     # Campaign Group 初始策略模块
├── docs/                             # 当前知识、全量扫描和外部研究
├── design-artifacts/                 # 历史产品愿景
├── _bmad-output/                     # 已完成规格和延期事项
├── .agents/
│   └── skills/                       # 119 个直接安装技能
└── _bmad/                            # 安装元数据、配置和共享运行资料
```

`.git/` 仅做仓库健康检查，不把对象库逐文件纳入项目内容评价。

## 当前业务区

```text
modules/amc_mta/
├── config.py                         # 窗口、阈值和字段常量
├── run_pipeline.py                   # 完整流水线入口
├── src/
│   ├── touchpoint_key.py             # 五段键解析与校验
│   ├── synthetic_event_pipeline.py   # 模拟用户事件及AMC/Ads/实体派生
│   ├── amc_path_builder.py           # 概念事件到匿名聚合路径
│   ├── amc_mta_attribution.py        # Markov、Shapley 与成本关联
│   └── model_comparison.py           # 差距、支持度、三项可靠性和治理推荐
├── scripts/                          # 各步骤 CLI
├── tests/                            # 6个测试文件，107项测试
├── data/simulated/                   # 1份模拟事实源及4类派生数据
├── outputs/attribution/              # 5 份正式生成输出
└── docs/                             # 数据、运行和治理契约
```

运行依赖方向为：

```text
config + touchpoint_key + simulated_touchpoints
          ↓
synthetic_event_pipeline（模拟数据）
          ├─ Ads / 触点实体聚合
          └─ 匿名概念事件
                    ↓
             amc_path_builder
          ↓
amc_mta_attribution
          ↓
model_comparison
          ↓
run_pipeline / scripts / outputs
```

## 知识与追溯区

```text
docs/
├── index.md                          # 全工作区主索引
├── project-overview.md               # 总体现状评价
├── architecture.md                   # 工作区级架构
├── source-tree-analysis.md           # 本文
├── component-inventory.md            # 组件和资产清单
├── workspace-file-management.md      # 文件位置、命名、归档和移动规则
├── development-guide.md              # 开发与验证指南
├── workspace-file-inventory.json     # 全量机器清单
├── amc-mta-*.md                      # 当前业务架构与评价
├── product/                          # 当前 AMC MTA 项目介绍
└── research/                         # PDF、DOCX、JSON、TXT 和研究笔记

design-artifacts/
└── A-Product-Brief/                  # 早期平台愿景、PRD、模型说明、补充与决策

_bmad-output/
└── implementation-artifacts/         # 已完成整改规格与延期事项
```

策略初始化模块结构：

```text
modules/mta_strategy_recommender/
├── data/simulated/                   # 两个输入 JSON：请求与候选池
├── outputs/initial_budget_recommendation.json # 唯一正式预算结果
├── docs/                             # 当前模型计划与输出契约
├── src/
│   ├── budget_recommender.py         # 数量、MTA bridge 与预算生成
│   └── hierarchy_validator.py        # AMC 血缘与预算结果复算
├── scripts/
│   ├── generate_initial_budget.py
│   └── validate_simulated_hierarchy.py
└── tests/
    └── test_hierarchy_validator.py   # 34 项合同、兼容与边界测试
```

## 安装工具区

`.agents/skills/` 是面向 Codex 的扁平技能安装目录。119 个一级技能目录均包含
`SKILL.md`；另有 1 个嵌套的 setup skill 模板。目录中大量相同知识文件是技能自包含
设计，不能按普通重复文件处理。

`_bmad/` 保存：

- 安装版本与模块来源；
- 2,075 条安装源文件清单；
- 119 条技能注册清单；
- 模块帮助表；
- 项目与个人配置；
- WDS 共享数据和 7 个 JavaScript 脚本；
- 配置解析脚本及测试。

技能实际运行文件位于 `.agents/skills/`，`_bmad/_config/skill-manifest.csv` 中的
源路径不是当前工作区内应存在的第二份技能副本。

## 文件组织判断

- 没有空文件、符号链接、子模块、缓存文件或未归位的业务资产。
- 生成型输出只保留 AMC 五份正式契约 CSV 与策略模块一份正式预算 JSON，其余
  `modules/*/outputs/` 内容被忽略。
- 本地个人覆盖 `_bmad/custom/config.user.toml` 已被正确忽略。
- 研究二进制文件集中在 `docs/research/`，没有混入业务运行目录。
- 历史文件没有删除，但通过索引和状态说明与当前能力隔离。

新增或移动文件必须遵循[工作区文件位置管理](workspace-file-management.md)。承担导航
职责的多文件或核心研究子目录统一用 `README.md` 作为入口；历史模型功能说明现位于
`design-artifacts/amc_mta/A-Product-Brief/`，不与当前产品介绍混放。
