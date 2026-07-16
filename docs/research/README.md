# Research Docs

这个目录保存项目研究资料、外部参考文件和数据源方案。这里的内容主要用于背景研究、方案判断和数据口径定义，不直接等同于可运行模型模块。

## Directory Map

```text
docs/research/
├── amazon/            # Amazon Ads / AMC 调研、方案和外部参考数据
├── ab-testing/        # A/B testing 与实验验证资料
├── mta/               # Multi-touch attribution 论文和学习笔记
├── machine-learning/  # Machine learning 背景资料
├── ontology/          # 本体论相关研究
└── industry/          # 行业资料和营销 AI 背景材料
```

## Boundary

- `research/` 放外部资料、调研结论、数据源分析和方案计划。
- `modules/` 放可运行模型代码、模块级输入样例、输出和使用文档。
- `design-artifacts/` 放 Product Brief、PRD、设计决策和产品侧说明。

Amazon AMC 的背景和数据链路放在：

```text
docs/research/amazon/amc/
```

Amazon API 调研文档与外部参考 JSON 放在：

```text
docs/research/amazon/research/
```

AMC MTA 的可运行样例数据放在 `modules/amc_mta/data/simulated/`，不放在研究目录。

MTA 模型的运行方式和输入输出 contract 放在：

```text
modules/mta/docs/
```
