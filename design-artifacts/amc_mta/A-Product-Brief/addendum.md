# Addendum: 模型与技术补充

> 历史愿景：本文是早期平台技术建议，不是当前代码契约。当前 AMC MTA 的实际模型
> 语义、输入和限制见[架构说明](../../../docs/amc_mta/amc-mta-architecture.md)与
> [数据契约](../../../modules/amc_mta/docs/amc-data-requirements.md)。

## 1. 推荐模型结构

本项目建议采用分层营销决策模型：

```text
MTA Attribution Layer
  -> ROI Analysis Layer
  -> Prediction Layer
  -> Optimization Layer
  -> Validation Layer
```

### 1.1 MTA Attribution Layer

目标是解释历史转化贡献。建议使用：

- Markov Chain Attribution：通过 removal effect 衡量渠道从用户路径中移除后对转化概率的影响。
- Shapley Value Attribution：从公平分配角度计算各渠道平均边际贡献。
- Bagged Logistic Regression Attribution：在数据量和特征丰富度足够时用于增强验证，降低共线性导致的不稳定。

MTA 输出包括 channel contribution、attributed conversions、attributed revenue、channel-level ROAS。

### 1.2 Prediction Layer

目标是预测给定 campaign 配置和预算下的未来表现。候选模型：

- Baseline：Ridge Regression、Random Forest。
- Enhanced：LightGBM、XGBoost、CatBoost。

预测目标可包括 conversions、revenue、CPA、ROAS。输入特征可包括 platform、region、industry、creative_type、spend、historical_ctr、historical_cvr、historical_cpc、seasonality。

注意：用于未来预测时，应避免把下一轮 campaign 开始前不可知的变量作为核心输入，例如实际 clicks、actual conversions。

### 1.3 Optimization Layer

目标是在业务约束下推荐预算组合。建议先采用 scenario simulation：

1. 生成候选预算组合。
2. 调用 Prediction Layer 预测每个组合的结果。
3. 根据目标函数排序，例如最大化 ROAS、最大化 profit、最大化 conversions 或最小化 CPA。
4. 应用约束，例如总预算固定、单渠道预算上下限、CPA 上限、预算调整幅度限制。

### 1.4 Validation Layer

A/B 测试或 geo split 用于验证模型建议。MVP 可以支持：

- 控制组使用当前预算组合。
- 实验组使用推荐预算组合。
- 对比 ROAS、CPA、conversion lift、revenue lift。

如果当前只有 campaign 聚合数据，可以先使用准实验方法，例如 region split、campaign split 或 pre/post analysis。

## 2. 数据限制与风险

如果输入数据只有 campaign/day 聚合粒度，它适合 ROI 分析、预测建模和预算模拟；但严格 MTA 通常需要用户级触点路径或 AMC 匿名聚合路径数据。

如果既无法获得用户级触点路径，也无法获得 AMC 匿名聚合路径，MVP 应清楚标记：

- MTA 结果为近似归因或示范归因。
- 预算建议基于历史聚合关系，不能被解释为确定性因果结论。
- A/B 或准实验结果优先作为模型校准依据。

## 3. 推荐 MVP 实现顺序

1. 数据导入与指标计算。
2. ROI dashboard。
3. 预测模型 baseline。
4. 预算 scenario simulation。
5. MTA 模块原型。
6. 实验设计与验证结果记录。
7. AI 问答解释层。
