---
title: Markov 移除效应
description: WeightedMarkovAttribution 的算法、公式和代码映射
lang: zh-CN
---

# Markov 移除效应

## 模型直觉 <span class="status-label status-verified" aria-label="Verified"></span>

一阶 Markov 链（First-order Markov Chain）把 `START`、每个触点、`CONVERSION` 和 `NULL` 看作状态。历史聚合路径提供状态之间的加权转移次数；归一化后得到转移概率。

如需了解包含转移型方法在内的数据驱动路径归因背景，可阅读 [Data-driven Multi-touch Attribution Models](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)。

`WeightedMarkovAttribution` 只依赖当前状态预测下一状态，因此不会记住更早的完整路径。

## 当前实现 <span class="status-label status-verified" aria-label="Verified"></span>

实现位置：`modules/amc_mta/src/amc_mta_attribution.py` 中的 `WeightedMarkovAttribution` 类。下面直接重现相关代码块，并逐行拆解。

实现分为五个明确部分：适配 AMC 聚合、盘点状态、估计转移、求解吸收概率，以及规范化移除效应。每个 Outcome 都通过同一算法的独立实例运行。

### 1. 将 AMC 聚合适配为加权状态路径

对于转化用户，`amc_rows_to_markov_rows()` 把一条 AMC 聚合拆成转化和未转化两类人群：

```python
base_path = [START, *touchpoints]                                  # 1
if converted_users > 0:                                            # 2
    rows.append({                                                   # 3
        "path": " > ".join([*base_path, CONVERSION]),              # 4
        "weight": float(converted_users),                           # 5
    })
null_weight = users - converted_users                              # 6
if null_weight > 0:                                                # 7
    rows.append({                                                   # 8
        "path": " > ".join([*base_path, NULL]),                    # 9
        "weight": null_weight,                                     # 10
    })
```

| 行 | 详细步骤 | 算法映射 | 原因 |
| --- | --- | --- | --- |
| 1 | 在观测触点序列前加上 `START` | 创建初始 Markov 状态 | 每条旅程都需要共同起点来计算转化概率 |
| 2-5 | 输出一条以 `CONVERSION` 结尾、按转化用户数加权的路径 | 增加转化转移质量 | 聚合行代表人群，因此一行必须按用户数计数，而不是只算一次路径观察 |
| 6 | 用 `users - converted_users` 推导未转化者 | 将聚合对账为两个互斥的终止人群 | 精确保留输入用户总数 |
| 7-10 | 当未转化质量为正时，输出一条以 `NULL` 结尾的路径 | 增加失败/流失转移质量 | 如果没有竞争性的吸收状态，每条连通路径最终转化概率都会无意义地等于一 |

对于 `purchase_count` 和 `revenue`，`amc_rows_to_outcome_markov_rows()` 只保留 Outcome 为正的路径，追加 `CONVERSION`，并以选定 Outcome 作为 `weight`。因此三个模型共享机制但不共享权重：转化用户归因建模“人和未转化者”，购买与收入归因则建模各自 Outcome 质量所经过的网络。

### 2. 盘点状态空间

构造函数只做确定性准备：

```python
self.path_rows = list(path_rows)                                    # 1
self.paths = [parse_path(str(row["path"])) for row in self.path_rows] # 2
self.touchpoints = sorted({                                         # 3
    state for path in self.paths for state in path                  # 4
    if state not in {START, CONVERSION, NULL}                       # 5
})
```

| 行 | 详细步骤 | 原因 |
| --- | --- | --- |
| 1 | 将输入序列物化 | 基准运行和每次移除运行都会重复遍历这些行 |
| 2 | 只解析一次序列化路径 | 转移估计应操作状态列表，而不是反复拆分字符串 |
| 3-5 | 收集非终止状态并排序 | 每个观测触点只移除一次，排序使输出顺序可复现 |

### 3. 构建加权转移矩阵

`transition_matrix()` 的关键循环是：

```python
for row, path in zip(self.path_rows, self.paths):                   # 1
    weight = safe_float(row.get("weight", row.get("users")))        # 2
    if weight <= 0:                                                 # 3
        continue
    for current, nxt in zip(path, path[1:]):                        # 4
        if current == removed_touchpoint:                           # 5
            break
        if nxt == removed_touchpoint:                               # 6
            counts[current][NULL] += weight                         # 7
            break
        counts[current][nxt] += weight                              # 8
for current, next_counts in counts.items():                         # 9
    total = sum(next_counts.values())                               # 10
    matrix[current] = {nxt: count / total for nxt, count in next_counts.items()} # 11
```

| 行 | 详细步骤 | 对 Markov 算法的映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 同时遍历每条聚合记录及其已解析路径 | 将路径拓扑与人群/Outcome 质量关联 | 聚合观察不能等权计数 |
| 2 | 优先使用明确的 Outcome 权重，否则回退到 users | 用一个转移引擎支持三个模型适配器 | 引擎不依赖某个特定 Outcome 列 |
| 3 | 忽略零质量行 | 零权重不能改变概率，反而可能制造空的转移总量 | 保证规范化有定义 |
| 4 | 把每条路径转成相邻有向边 | 实现一阶假设 | 下一状态分布只由当前状态决定 |
| 5 | 如果遍历已到达被删除节点，就停止 | 移除该触点的全部出站行为 | 已删除状态不能继续传递概率 |
| 6-7 | 将进入被删除节点的边重定向到 `NULL`，然后停止 | 当路径依赖被删除触点时实现失败 | 直接删除节点并连接前后邻居会虚构从未观测到的转移 |
| 8 | 把完整行权重加到观测边 | 构建加权转移次数 | 矩阵代表质量，而不只是不同路径形状 |
| 9-11 | 规范化每个当前状态的出站次数 | 生成行和为一的条件概率 | 吸收迭代需要概率而不是次数 |

### 4. 求解最终转化概率

`conversion_probability()` 对转移矩阵执行不动点迭代：

```python
values = {state: 0.0 for state in states}                            # 1
values[CONVERSION] = 1.0                                            # 2
values[NULL] = 0.0                                                  # 3
for _ in range(1000):                                               # 4
    max_delta = 0.0                                                 # 5
    next_values = dict(values)                                      # 6
    for state in states:                                            # 7
        if state in {CONVERSION, NULL}:                             # 8
            continue
        prob = sum(p * values.get(nxt, 0.0)                          # 9
                   for nxt, p in matrix.get(state, {}).items())
        max_delta = max(max_delta, abs(prob - values.get(state, 0.0))) # 10
        next_values[state] = prob                                   # 11
    values = next_values                                            # 12
    if max_delta < 1e-12:                                           # 13
        break
return values.get(START, 0.0)                                      # 14
```

| 行 | 详细步骤 | 算法映射与原因 |
| --- | --- | --- |
| 1-3 | 未知状态初始化为零，转化设为一，空状态设为零 | 这是最终吸收问题的边界条件 |
| 4 | 将求解限制在 1,000 次迭代内 | 防止错误或不收敛的图阻塞流程 |
| 5 | 重置本轮观测到的最大变化 | 每次完整更新分别判断收敛 |
| 6 | 更新前复制上一轮 | 形成同步更新：每个新值都使用同一旧向量，不受集合迭代顺序影响 |
| 7-8 | 只更新瞬态状态 | 吸收边界值必须保持固定 |
| 9 | 执行 `value(state) = sum(P(state,next) * value(next))` | 这是最终转化概率的 Bellman 型不动点方程 |
| 10-11 | 记录最大变化并保存新概率 | 最大范数直接检验全部状态是否收敛 |
| 12-13 | 提交本轮，并在小于 `1e-12` 时停止 | 不求矩阵逆的情况下，得到足以稳定计算后续移除差异的精度 |
| 14 | 读取共同初始状态的概率 | 这是模型的整体最终转化概率 |

如果存在瞬态状态且达到迭代上限，函数会抛出错误，而不会发布质量未知的近似结果。

### 5. 将移除效应转换为归因份额

```python
base_prob = self.conversion_probability()                            # 1
for touchpoint in self.touchpoints:                                 # 2
    removed_prob = self.conversion_probability(                     # 3
        removed_touchpoint=touchpoint)
    effects[touchpoint] = max(base_prob - removed_prob, 0.0)        # 4
total_effect = sum(effects.values())                                # 5
if total_effect <= 0:                                               # 6
    equal_share = 1 / len(self.touchpoints) if self.touchpoints else 0.0 # 7
    return {touchpoint: equal_share for touchpoint in self.touchpoints} # 8
return {touchpoint: effect / total_effect for touchpoint, effect in effects.items()} # 9
```

| 行 | 详细步骤 | 算法映射与原因 |
| --- | --- | --- |
| 1 | 对完整网络求解一次 | 建立反事实参照概率 |
| 2-3 | 逐个移除触点，重建并求解网络 | 对每个节点施加相同的移除干预 |
| 4 | 取非负概率损失 | 定义移除效应，并避免数值或结构性上升变成负归因 |
| 5 | 汇总全部效应 | 建立规范化分母 |
| 6-8 | 仅在所有触点都没有正移除效应时等分 | 在退化但非空的模型中仍提供完整 share 向量 |
| 9 | 规范化正效应 | 生成总和为一的份额 |

### 6. 编排三个独立 Outcome 模型

`run_markov_attribution()` 为 `converted_users`、`purchase_count` 和 `revenue` 构造独立实例，合并各实例的触点集合，计算每个模型的 share，再将 share 乘以原始 Outcome 总量。分离十分重要：Amazon Marketing Cloud 的购买 Outcome 永远不与 Amazon Ads 的诊断转化相加，收入权重也永远不会改变转化用户的转移次数。

## 公式

对触点 (t)：

$$
\text{removal effect}(t)
= \max\left(
\text{base conversion probability}
- \text{conversion probability without } t,
0
\right)
$$

归因份额为：

$$
\text{Markov share}(t)
= \frac{\text{removal effect}(t)}
{\sum_j \text{removal effect}(j)}
$$

## 如何解释 <span class="status-label status-inference" aria-label="Inference"></span>

较高份额表示：在当前历史转移网络中，移除该触点后模型估计的转化概率下降更多。它是观察性路径关联，不是随机实验得到的增量收益。

## 代码输出 <span class="status-label status-verified" aria-label="Verified"></span>

`run_markov_attribution()` 为转化用户、购买次数和收入分别构建加权 Markov 模型，最终写入 `amc_markov_attribution_results.csv`。成本通过标准化触点键从 Amazon Ads 风格日报聚合，不参与 Markov 转移概率训练。

## 参考资料

- [Data-driven Multi-touch Attribution Models（PDF）](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)
