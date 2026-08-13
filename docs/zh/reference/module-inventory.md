---
title: 模块清单
lang: zh-CN
---

# 模块清单

`modules/` 保存当前可运行的业务实现。每个模块自行管理代码、输入、输出、测试和使用文档。

| 模块 | 用途 | 状态 | 入口 |
| --- | --- | --- | --- |
| AMC MTA | 基于 AMC 匿名聚合路径进行五段互动粒度归因和双模型诊断 | 可运行归因模块 | [AMC MTA 模块](../attribution/amc-mta-module.md) |
| MTA Strategy Initializer | 以 Campaign Group 为顶层生成新 Ad Group 数量和预算初始点 | 可运行生成器、正式输出与校验已实现 | [策略初始化器](../strategy_recommendation/module-overview.md) |

## 目录约定

```text
modules/<module>/
├── data/       # 模块专用输入和样例
├── docs/       # 数据契约和使用说明
├── outputs/    # 可再生运行结果
├── scripts/    # 命令行脚本
├── src/        # 核心实现
└── tests/      # 自动化测试（若有）
```

当前架构、能力评价和阅读顺序见[中文文档首页](/zh/)。外部论文和参考资料放在 `docs/research/`，不与模块运行输入混放。

两个模块的边界是：AMC MTA 输出 Group 范围内的五段触点证据；策略初始化器针对一个
Campaign Group 下固定的四个 Campaign，只产生新 Ad Group 数量与预算 `INITIAL_SEED`，
不分配具体候选，也不承担后续优化。

已删除的旧通用 MTA 模块不属于当前项目范围，不恢复、不评价，也不作为新开发入口。
