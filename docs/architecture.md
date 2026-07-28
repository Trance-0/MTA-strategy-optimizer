# 工作区级架构

## 架构定位

本仓库采用“业务数据流水线 + 版本化知识库 + 内嵌开发工具链”的三层结构，不是
Web 服务、数据库应用或可部署平台。

```text
外部研究与历史意图
docs/research + design-artifacts + _bmad-output
                     │
                     ▼
当前知识与治理层
docs + modules/*/docs
                     │
                     ▼
业务执行与初始化层
modules/amc_mta → five-part attribution evidence
                        ↓
modules/mta_strategy_recommender → INITIAL_SEED

.agents + _bmad 为开发辅助平面，不参与归因计算
```

## 业务执行架构

AMC MTA 是纯 Python 标准库数据流水线：

1. 概念事件样例构建 AMC 风格匿名聚合路径；
2. 严格校验五段触点键和路径结果；
3. 独立运行 Markov 与 Path-level Shapley；
4. 关联五段 Amazon Ads 成本与平台指标；
5. 生成触点差异、整体摘要和治理推荐。

没有网络请求、数据库、API 端点、认证、后台任务或 UI。详细算法与数据流见
[AMC MTA 架构](amc_mta/amc-mta-architecture.md)。

策略初始化器同样只使用 Python 标准库。它不改变 MTA 五段键，而是以 Campaign Group
为顶层，校验四个固定 Campaign、冻结候选池和 `Ad Group → Keyword/SKU` 初始分配。
Campaign 记录持有单值 `ad_product`，Ad Group 不重复保存该字段。

## 知识架构

事实优先级：

```text
运行代码与测试
  > 模块数据/治理契约
  > 可再生输出
  > 当前架构与能力评价
  > 项目介绍
  > 研究笔记
  > 历史产品文档与冻结规格
```

这条优先级解决了历史愿景比当前实现更宽、旧规格记录过去字段与粒度的问题。
文件职责、稳定入口和归档流程由
[工作区文件位置管理](workspace-file-management.md)统一约束。

## 工具架构

```text
_bmad/config*.toml + module config
                 ↓
_bmad/_config manifests
                 ↓ install/registration
.agents/skills/<skill>/SKILL.md + resources/scripts
                 ↓
Codex/BMad workflows
                 ↓
docs、design-artifacts、_bmad-output 或源码改动
```

工具平面与业务平面之间只有“开发者调用工具修改或审查项目”的关系。AMC
`run_pipeline.py` 不导入 `.agents` 或 `_bmad`。

## 技术栈

| 区域 | 技术 | 说明 |
| --- | --- | --- |
| AMC MTA | Python 3.10+ 标准库 | CSV 数据流水线、算法、测试 |
| BMad 配置 | TOML、YAML、CSV、Markdown | 安装与工作流元数据 |
| BMad 脚本 | Python、Bash | 配置解析、技能生成与自动化 |
| WDS 辅助 | Node.js JavaScript | 文档/设计资产操作脚本 |
| 文档 | CommonMark、JSON、PDF、DOCX | 项目知识与研究资料 |
| 版本控制 | Git | 当前无 CI/CD 配置 |

## 数据与安全边界

- 当前业务输入和输出均为仓库内模拟 CSV。
- `.env`、本地覆盖、缓存和普通生成输出由 `.gitignore` 隔离。
- 未发现实际 API key、私钥或凭证；技能知识文件中的 password/token 字样为示例。
- AMC 概念事件只用于本地演示，不代表真实 AMC 可导出用户级事件。
- 没有生产部署、密钥管理、数据保留或 AMC 隐私执行实现。

## 架构缺口

- 没有依赖锁文件、统一任务入口或 CI。
- 没有真实 AMC 查询定义及隐私阈值执行证据。
- 没有滚动窗口、重采样和跨时间稳定性数据层。
- 工具测试没有统一环境声明，至少一项需要未安装的 `pytest`。
- standalone module scaffold 的插件命名实现与测试断言不一致。
