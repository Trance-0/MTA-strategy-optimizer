---
title: 环境设置
description: 本地运行、文档开发和目录职责
lang: zh-CN
---

# 环境设置

## 前置条件 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

- Python 3.11 或更新版本。
- Node.js 20 或更新的长期支持版本，以及 npm。
- Git；仅在需要同步远程仓库时使用网络访问。

当前 Python 模块仅使用标准库。文档依赖保存在 `docs/package-lock.json`。

当前 AMC MTA CSV 读取器使用 Python 的进程默认文本编码，而演示 CSV 是 UTF-8。
Windows 使用非 UTF-8 系统区域设置时，应在运行下方 Python 命令前启用 UTF-8 模式：

```powershell
$env:PYTHONUTF8 = "1"
```

也可以使用 `python -X utf8 ...`。否则中文说明行可能触发 `UnicodeDecodeError`。

## 运行归因与策略模块 <span class="status-label status-verified" aria-label="Verified"></span>

从仓库根目录运行：

```bash
python -B modules/amc_mta/run_pipeline.py
python modules/amc_mta/scripts/validate_data_alignment.py
python -B -m unittest discover -s modules/amc_mta/tests -p "test_*.py"

python -B modules/mta_strategy_recommender/scripts/generate_initial_budget.py --check-output
python modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python -B -m unittest discover -s modules/mta_strategy_recommender/tests -p "test_*.py"
```

## 本地文档站 <span class="status-label status-verified" aria-label="Verified"></span>

```bash
cd docs
npm install
npm run dev
```

打开终端显示的本地地址。文档正文中的 PDF 参考链接会直接打开 `docs/research/` 原位置中的文件；开发服务器不会要求把这些文件移动到 `public/`。

其他命令：

```bash
npm run build          # 生成静态站点并复制研究附件
npm run preview        # 预览生产构建
npm run cloudflare:dev # 使用 Wrangler 测试 Cloudflare Worker
```

Windows 也可运行 `run-doc-site.bat dev`，macOS/Linux 可运行 `sh run-doc-site.sh dev`。

## 目录速查 <span class="status-label status-verified" aria-label="Verified"></span>

| 目录 | 什么时候使用 |
| --- | --- |
| `modules/amc_mta/src/` | 修改归因算法和聚合逻辑 |
| `modules/amc_mta/scripts/` | 生成、运行、比较或验证归因产物 |
| `modules/amc_mta/data/simulated/` | 查看本仓库的合成演示输入 |
| `modules/amc_mta/outputs/` | 查看当前归因输出 |
| `modules/mta_strategy_recommender/src/` | 修改预算初始化逻辑 |
| `modules/mta_strategy_recommender/data/simulated/` | 查看策略请求和候选池 |
| `modules/mta_strategy_recommender/outputs/` | 查看正式初始预算 JSON |
| `docs/.vitepress/` | 修改站点配置和主题 |
| `docs/research/` | 保存并在站点中展示研究附件；不是运行输入 |

不要把凭据、客户级数据、生产账户标识或真实生成数据提交到本仓库。
