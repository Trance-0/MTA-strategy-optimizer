---
title: AI驱动营销投放优化平台
status: draft
created: 2026-06-20
updated: 2026-06-20
---

# PRD: AI驱动营销投放优化平台

## 0. Document Purpose

本文档面向产品、数据分析、UX、架构和后续 BMAD 实现流程，定义 `marketing-roi-analysis` 项目的 MVP 产品需求。本文档基于现有 Product Brief、MTA 学习笔记和模型讨论生成，重点描述产品能力、用户价值、功能需求、非功能要求、MVP 范围、成功指标与开放问题。模型技术细节与算法选择补充见 `addendum.md`。

## 1. Vision

AI驱动营销投放优化平台帮助营销团队从“凭经验调预算”转向“用数据解释、预测和验证投放决策”。平台先解释历史 campaign 中各渠道对转化和收入的贡献，再预测下一轮 campaign 在不同预算组合下的表现，最后给出可执行的预算优化建议。

本产品不是普通广告报表。普通报表回答“发生了什么”，本产品进一步回答“为什么发生”“如果下次这样投会怎样”“应该怎么调整”。它把 MTA 归因、ROI 分析、效果预测、预算优化和实验验证连接成一条决策链路。

MVP 的目标是形成一个可演示、可解释、可迭代的营销 ROI 分析工具，让用户能够上传或接入 campaign 数据，查看渠道表现，模拟预算调整，获得下一轮 campaign 的推荐投资组合，并理解推荐背后的原因与风险。

## 2. Target User

### 2.1 Jobs To Be Done

- 数字营销负责人需要判断不同渠道的真实贡献，并决定下一轮预算如何分配。
- 广告投放团队需要快速发现高 ROI 和低 ROI 的渠道、地区、创意组合。
- 数据分析师需要用可解释模型把投放数据转化为可信业务结论。
- 业务决策者需要在预算会议中看到清晰的 ROI、风险和推荐依据。

### 2.2 Non-Users (v1)

- 不面向需要自动媒体采购和自动出价执行的广告交易团队。
- 不面向创意生产团队，MVP 不提供广告素材生成和创意工作流。
- 不面向需要完整企业 BI 权限体系和复杂审批流的大型组织。

### 2.3 Key User Journeys

- **UJ-1. Emma 复盘上一轮 campaign 并找出预算浪费点。**
  Emma 是数字营销负责人，刚结束一轮 TikTok 与 Meta 投放。她进入 Web dashboard，上传 campaign 数据，查看 spend、revenue、ROAS、CPA 和渠道贡献。系统突出显示 Meta 在部分 region 的 CPA 偏高，而 TikTok 的 UGC 创意组合 ROAS 更好。她导出复盘结论用于团队会议。

- **UJ-2. Daniel 模拟下一轮 campaign 的预算组合。**
  Daniel 是广告投放经理，需要规划下个月预算。他输入总预算、候选平台和业务约束，例如单平台预算不超过 70%、CPA 不能高于目标值。系统生成多个预算方案，预测每个方案的 conversions、revenue、CPA 和 ROAS，并推荐预计表现最好的组合。

- **UJ-3. Priya 解释为什么系统建议增加 TikTok 预算。**
  Priya 是数据分析师，需要向业务团队解释模型建议。她打开推荐详情，看到 MTA 贡献、历史 ROI、预测结果、边际收益和风险提示。她通过 AI 问答询问“为什么不是继续增加 Meta 预算”，系统用数据解释 Meta 在特定 region 和 creative_type 下存在效率下降。

- **UJ-4. Michael 验证模型推荐是否真实有效。**
  Michael 是业务决策者，不希望直接把全部预算转向模型推荐方案。他创建一个实验验证计划：控制组使用原预算组合，实验组使用推荐组合。平台记录实验目标、分组、指标和结果，用于后续判断推荐是否有效。

## 3. Glossary

- **Campaign** — 一次营销投放活动，由平台、地区、行业、创意类型、预算、曝光、点击、转化和收入等数据组成。
- **Channel** — 营销渠道或平台，例如 TikTok、Meta、Google Ads。
- **Touchpoint** — 用户在转化前接触到的营销触点。
- **MTA** — Multi-Touch Attribution，多触点归因，用于分配多个 Touchpoint 对转化的贡献。
- **Attributed Revenue** — 经归因模型分配到某个 Channel 的收入。
- **ROAS** — Return On Ad Spend，广告收入除以广告花费。
- **CPA** — Cost Per Acquisition，广告花费除以转化数。
- **Effect Prediction** — 效果预测，给定一个 campaign 或预算方案，预测未来 conversions、revenue、CPA 和 ROAS。
- **Budget Optimization** — 预算优化，在多个候选方案中选择满足业务约束且预计表现最好的预算组合。
- **Scenario Simulation** — 方案模拟，生成并评估多个预算组合。
- **Validation Experiment** — 验证实验，通过 A/B 测试、geo split 或准实验方法验证推荐方案。
- **Recommendation** — 系统生成的下一轮 campaign 预算或策略建议。

## 4. Features

### 4.1 数据导入与指标标准化

**Description:** 用户可以导入 campaign 数据，系统完成字段识别、基础校验和指标标准化，为后续 ROI、MTA、预测和优化提供统一数据基础。MVP 支持 CSV 文件导入。[ASSUMPTION: v1 首先使用 CSV 导入，后续再接广告平台 API。] Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-1: CSV 数据导入

用户可以上传包含 campaign 指标的 CSV 文件。

**Consequences (testable):**
- 系统接受至少包含 date、platform、region、industry、creative_type、impressions、clicks、conversions、spend、revenue 的 CSV。
- 系统在缺少必填字段时提示缺失字段名称。
- 系统在导入成功后展示数据行数、日期范围、平台数量和总 spend。

#### FR-2: 指标计算与标准化

系统可以计算并标准化 CTR、CVR、CPC、CPA、CPM、ROAS 等指标。

**Consequences (testable):**
- 当原始 CSV 未包含派生指标时，系统自动计算。
- 当 spend 或 conversions 为 0 时，系统不产生崩溃，并显示空值或明确的不可计算状态。
- 系统保留原始字段和标准化字段，支持后续模型调用。

### 4.2 MTA 归因分析

**Description:** 系统基于历史转化路径或可用 campaign 数据，估算不同 Channel 对转化和收入的贡献。MVP 支持 Markov Chain 和 Shapley Value 的归因结果展示；当缺少用户级路径数据时，系统必须标记结果限制。[ASSUMPTION: MVP 可能先使用聚合数据进行示范归因，用户级路径数据将在后续版本接入。] Realizes UJ-1, UJ-3.

**Functional Requirements:**

#### FR-3: 渠道贡献计算

系统可以输出每个 Channel 的 contribution share、attributed conversions 和 attributed revenue。

**Consequences (testable):**
- 系统展示每个 Channel 的贡献占比，且总贡献占比合计为 100% 或展示舍入误差说明。
- 系统可以按 platform、region、creative_type 过滤归因结果。
- 系统在数据不足时显示“归因可信度受限”的提示。

#### FR-4: 多模型归因对比

用户可以比较至少两种 MTA 方法的渠道贡献结果。

**Consequences (testable):**
- 系统展示 Markov Chain 和 Shapley Value 的结果差异。
- 系统突出显示模型结论一致和不一致的 Channel。
- 系统为不一致结果提供解释入口，例如数据稀疏、渠道协同或路径缺失。

### 4.3 ROI 分析 Dashboard

**Description:** 系统将 spend、revenue、conversions、CPA、ROAS 与 MTA 贡献结合，帮助用户判断历史投放效率。Realizes UJ-1, UJ-3.

**Functional Requirements:**

#### FR-5: 渠道级 ROI 展示

用户可以查看 Channel、region、industry、creative_type 维度下的 ROI 表现。

**Consequences (testable):**
- 系统展示 spend、revenue、conversions、CPA、ROAS。
- 用户可以按日期范围、platform、region、industry、creative_type 过滤。
- 系统可以按 ROAS、CPA、spend、revenue 排序。

#### FR-6: 低效投放识别

系统可以识别表现异常或低效的投放组合。

**Consequences (testable):**
- 系统标记高 spend 低 ROAS 的组合。
- 系统标记 CPA 高于目标阈值的组合。
- 用户可以查看低效组合对应的历史趋势和可能原因。

### 4.4 效果预测

**Description:** 用户输入下一轮 campaign 的候选配置或预算方案，系统预测该方案的 conversions、revenue、CPA 和 ROAS。效果预测的职责是评价一个具体方案，而不是直接选择最优方案。Realizes UJ-2, UJ-3.

**Functional Requirements:**

#### FR-7: 单方案效果预测

用户可以输入一个 campaign 方案，系统返回预测指标。

**Consequences (testable):**
- 用户可以输入 platform、region、industry、creative_type、spend 等字段。
- 系统输出 predicted conversions、predicted revenue、predicted CPA、predicted ROAS。
- 系统展示预测置信提示或风险说明，不把预测结果表述为确定结果。

#### FR-8: 边际收益提示

系统可以提示预算增加后的潜在边际收益变化。

**Consequences (testable):**
- 当某 Channel 预算增加但 predicted ROAS 下降时，系统显示边际收益递减提示。
- 用户可以查看不同 spend 水平下的预测曲线或表格。
- 系统区分“历史 ROAS 高”和“继续加预算后仍然高”这两个概念。

### 4.5 预算优化

**Description:** 系统在总预算和业务约束下生成多个候选预算组合，调用效果预测能力逐一评估，并推荐预计表现最好的下一轮营销投资组合。预算优化的职责是比较多个方案并选择方案。Realizes UJ-2.

**Functional Requirements:**

#### FR-9: 预算约束输入

用户可以设置预算优化的目标和约束。

**Consequences (testable):**
- 用户可以输入 total budget。
- 用户可以设置优化目标，包括最大化 ROAS、最大化 revenue、最大化 conversions 或最小化 CPA。
- 用户可以设置单 Channel 最小和最大预算比例。
- 用户可以设置 CPA 上限或 ROAS 下限。

#### FR-10: 预算方案生成与评分

系统可以生成多个候选预算组合，并预测每个组合的结果。

**Consequences (testable):**
- 系统展示候选方案列表，包括预算分配、predicted conversions、predicted revenue、predicted CPA、predicted ROAS。
- 系统标记推荐方案和备选方案。
- 系统显示每个方案满足或违反的业务约束。

#### FR-11: 推荐理由解释

系统可以解释为什么推荐某个预算组合。

**Consequences (testable):**
- 推荐详情至少包含历史 ROI、预测结果、边际收益和约束满足情况。
- 系统说明不推荐其他高风险方案的原因。
- 用户可以导出推荐摘要。

### 4.6 验证实验设计

**Description:** 系统支持用户为模型推荐方案创建验证计划，记录实验组、控制组、核心指标和结果。MVP 不负责真实广告流量分配，只负责实验设计、记录和结果对比。Realizes UJ-4.

**Functional Requirements:**

#### FR-12: 验证计划创建

用户可以为 Recommendation 创建 A/B 测试、geo split 或准实验验证计划。

**Consequences (testable):**
- 用户可以选择控制组和实验组描述。
- 用户可以设置 primary metric，例如 ROAS、CPA、conversion lift、revenue lift。
- 用户可以记录实验开始和结束日期。

#### FR-13: 验证结果记录

用户可以录入实验结果并查看是否支持 Recommendation。

**Consequences (testable):**
- 系统展示控制组和实验组的核心指标对比。
- 系统标记结果为支持、不支持或证据不足。
- 系统将验证结果关联回原 Recommendation。

### 4.7 AI 问答与业务解释

**Description:** 用户可以用自然语言询问投放表现、归因结果、预测结果和推荐理由。AI 回答必须引用平台内已有数据和模型输出，避免无依据结论。Realizes UJ-3.

**Functional Requirements:**

#### FR-14: 自然语言问题回答

用户可以询问营销 ROI 相关问题。

**Consequences (testable):**
- 系统支持问题如“为什么 TikTok 比 Meta 表现好”“下个月预算怎么分”“哪个 region CPA 最高”。
- 回答包含相关指标或推荐依据。
- 当数据不足时，回答明确说明限制。

#### FR-15: 推荐解释生成

系统可以把模型结果转化为业务语言。

**Consequences (testable):**
- 系统输出适合营销团队理解的摘要。
- 系统避免只展示模型术语，不解释业务含义。
- 系统在回答中区分历史事实、模型预测和实验验证结果。

## 5. Cross-Cutting NFRs

- **Explainability:** 所有 Recommendation 必须展示关键依据，至少包括历史 ROI、预测指标、约束条件和主要风险。
- **Data Quality:** 系统必须对缺失字段、异常值、除零指标和日期范围异常给出明确提示。
- **Performance:** MVP 数据量在 10 万行以内时，导入、过滤和基础指标计算应在可交互时间内完成。[ASSUMPTION: MVP 面向 demo 和中小型数据集。]
- **Reliability:** 模型无法运行或数据不足时，系统必须降级为可解释错误状态，不能输出伪确定性建议。
- **Privacy:** MVP 不应要求导入个人身份信息；如未来接入用户级路径数据，应进行去标识化处理。
- **Auditability:** Recommendation、输入约束、模型版本和验证结果应可追溯。

## 6. Constraints and Guardrails

- 系统不得把预测结果表述为确定结果。
- 系统不得把历史 ROI 直接等同于未来 ROI。
- 系统必须明确区分 MTA 归因、效果预测、预算优化和实验验证。
- 当只有 campaign 聚合数据时，系统不得宣称完成严格用户级 MTA。
- 预算优化建议必须展示业务约束，避免推荐不可执行方案。

## 7. Non-Goals (Explicit)

- MVP 不自动购买广告、不自动出价、不自动修改广告平台预算。
- MVP 不生成广告素材、不评估创意内容质量。
- MVP 不建设完整企业权限、审批、审计和 SSO 系统。
- MVP 不保证预测结果真实发生。
- MVP 不替代真实 A/B 测试或业务判断。
- MVP 不做完整数据仓库和实时流处理平台。

## 8. MVP Scope

### 8.1 In Scope

- CSV 数据导入。
- campaign 指标标准化与 ROI dashboard。
- 渠道贡献与 MTA 结果展示。
- Markov Chain 与 Shapley Value 归因对比。
- 单方案效果预测。
- 预算 scenario simulation。
- 带约束的预算推荐。
- 推荐理由解释。
- A/B、geo split 或准实验验证计划记录。
- AI 问答解释层。

### 8.2 Out of Scope for MVP

- 广告平台 API 实时接入，延期到 v2。
- 自动执行预算调整，延期到 v2/v3。
- 完整用户级实验平台，延期到 v2/v3。
- 企业级权限与审批流，延期到 v2。
- 多租户 SaaS 计费系统，延期到 v3。

## 9. Success Metrics

**Primary**

- **SM-1:** 用户可以从导入数据到生成预算 Recommendation 完成端到端流程，目标是在 demo 数据上 10 分钟内完成。Validates FR-1, FR-2, FR-9, FR-10, FR-11.
- **SM-2:** Recommendation 必须包含可解释依据，目标是 100% 推荐包含历史 ROI、预测结果、约束和风险提示。Validates FR-11, FR-15.
- **SM-3:** 效果预测模块可以对候选方案输出 conversions、revenue、CPA 和 ROAS。Validates FR-7, FR-8.

**Secondary**

- **SM-4:** 用户可以比较至少两种归因方法的 Channel contribution。Validates FR-3, FR-4.
- **SM-5:** 用户可以创建并记录至少一种验证实验计划。Validates FR-12, FR-13.
- **SM-6:** AI 问答可以回答至少 10 个常见营销 ROI 问题，并明确区分历史、预测和验证。Validates FR-14, FR-15.

**Counter-metrics (do not optimize)**

- **SM-C1:** 不以单次预测 ROAS 最大化作为唯一目标，避免推荐过度集中到单一 Channel。
- **SM-C2:** 不以模型复杂度作为成功指标，优先保证可解释、可验证和可演示。
- **SM-C3:** 不以归因贡献占比“看起来精确”为目标，必须展示数据限制和可信度提示。

## 10. Risks and Mitigations

- **Risk:** 当前数据可能是 campaign 聚合数据，不足以支持严格用户级 MTA。  
  **Mitigation:** MVP 标记归因限制，优先将 MTA 作为可解释分析模块；后续接入用户级路径数据。

- **Risk:** 预测模型可能过拟合历史 campaign。  
  **Mitigation:** 使用训练/验证拆分、时间切分验证、baseline 对比和预测误差展示。

- **Risk:** 预算优化可能推荐业务上不可执行的极端方案。  
  **Mitigation:** 必须支持单 Channel 上限、下限、CPA 上限、调整幅度限制。

- **Risk:** 用户可能把预测建议误解为因果结论。  
  **Mitigation:** 文案和解释层明确区分历史相关性、模型预测和实验验证。

- **Risk:** A/B 测试成本高，MVP 无法真实控制广告流量。  
  **Mitigation:** MVP 先支持实验设计与结果记录，允许 geo split 或准实验作为替代。

## 11. Data Governance

- MVP 默认不处理 PII。
- 用户级路径数据如后续接入，应去标识化，并记录数据来源、字段含义和保留周期。
- 系统应记录每次 Recommendation 使用的数据版本、模型版本和约束输入。
- AI 问答不得编造不存在的数据来源或实验结果。

## 12. Open Questions

1. MVP 最终是否只面向 Web dashboard，还是还需要 Notebook/report 形式输出？
2. 是否能够获得用户级 Touchpoint 路径数据，还是只有 campaign/day 聚合数据？
3. 预算优化的默认目标应该是最大化 ROAS、最大化 revenue，还是最大化 profit？
4. 是否需要把 Google Ads 加入 MVP，还是先聚焦 TikTok vs Meta？
5. 是否需要支持行业、地区、创意类型的固定筛选维度，还是允许用户自定义维度？
6. AI 问答是否需要接入 OpenAI API，还是先用本地规则和模板生成解释？
7. MVP 是否需要生成 PPT 或 PDF 汇报材料？

## 13. Assumptions Index

- §4.1 — v1 首先使用 CSV 导入，后续再接广告平台 API。
- §4.2 — MVP 可能先使用聚合数据进行示范归因，用户级路径数据将在后续版本接入。
- §5 — MVP 面向 demo 和中小型数据集。

