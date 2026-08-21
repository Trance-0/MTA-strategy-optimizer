# Demo 接入说明：BrandLens + SK-II GMV NN

| 项 | 内容 |
|----|------|
| Demo | `AI-MTA-仇涵-1786085710_demo 3.0.html`（备份 `.bak`；另存 `…3.1-gmv.html`） |
| 模型 | Extended-27 **MLP** 权重 `results/demo_mlp_extended27.json` |
| 导出 | `python3 code/export_demo_weights.py` |

## 能力边界

| Demo 原能力 | 本次接入 |
|-------------|---------|
| Campaign / Ad group 预算重配 + ROAS 情景 | **未替换**（仍为模拟） |
| 新增 **GMV Forecast** 页 | 真实 NN：四类预算 + P0 结构 → 归因交易额 |

## 使用

1. 浏览器打开 `AI-MTA-仇涵-1786085710_demo 3.0.html`
2. 左侧 **GMV Forecast**
3. 调 SP/SB/SD/DSP 与结构占比 → 即时预测；右侧含「全预算 +10%」对照

## 复现权重

```bash
cd _bmad-output/implementation-artifacts/asin-gmv-nn
python3 code/export_demo_weights.py
# 再运行本目录旁的 HTML 打包脚本，或手动把 JSON 嵌回页面
```
