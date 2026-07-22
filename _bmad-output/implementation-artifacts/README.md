# 实现产物

本目录是工作流追溯区，不是 AMC MTA 运行依赖。为保持冻结规格和既有引用稳定，
规格与延期正文不移动；本 README 原位提供“已完成规格”“当前整理”和“待办”
三个分类视图。

## 已完成规格

| 规格 | 状态 |
| --- | --- |
| [全链路升级为五段互动粒度](spec-add-interaction-type-granularity-2.md) | done |
| [在 AMC 推荐输出中增加最终推荐值](spec-add-recommended-value-field.md) | done |
| [为 AMC 路径样例增加中文字段注释](spec-annotate-amc-path-report.md) | done |
| [根据新增数据自动识别窗口并输出](spec-auto-detect-amc-report-window.md) | done |
| [从 AMC MTA 全链路删除售出件数字段](spec-remove-units-sold.md) | done |
| [全量评估 AMC MTA 双模型输出](spec-evaluate-all-mta-outputs.md) | done |
| [将模拟数据扩展为完整一年](spec-expand-amc-sample-to-one-year.md) | done |
| [AMC MTA 治理输出仅保留五粒度](spec-five-part-only-model-governance.md) | done |
| [精简 AMC MTA 模型比较输出字段](spec-simplify-amc-output-fields.md) | done |
| [简化 AMC MTA 可靠性判断并写入输出](spec-simplify-amc-reliability-judgment.md) | done |

## 当前整理

- [整理 AMC MTA Markdown 提交包](spec-prepare-amc-mta-submission-package.md) — done
- [全工作区清理与一致性修复](spec-clean-workspace.md) — done
- [将项目整理为单一 AMC MTA 归因能力](spec-focus-project-on-amc-mta.md) — done
- [整理并建立工作区文件位置治理](spec-organize-workspace-files.md) — done

## 待办

- [延期事项](deferred-work.md)

规格文件用于记录实现意图、边界、代码映射和验证结果；当前有效的运行说明以模块 README 和模块文档为准。

冻结规格是获批时的历史快照。索引中的链接保持有效，但规格正文中的旧路径不保证
反映当前目录结构，也不会仅为修复历史链接而改写。
