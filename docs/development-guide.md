# 开发与验证指南

## 环境

- Python 3.10 或更高版本；
- Node.js，仅用于检查或运行 `_bmad/wds/scripts/`；
- Git；
- AMC MTA 本身不需要安装第三方 Python 包。

安装工具的部分测试使用 `pytest`，但仓库当前没有统一依赖文件。除非需要维护
`.agents` 工具代码，否则不必为运行 AMC MTA 安装它。

## 运行业务流水线

```bash
python3 -B modules/amc_mta/run_pipeline.py
python3 modules/amc_mta/scripts/validate_data_alignment.py
```

流水线以 Amazon Ads 输入的最早至最晚 `reportDate` 自动确定窗口，不应为新增数据
修改配置日期。自定义输入与输出参数见 `modules/amc_mta/docs/usage.md`。

输出位置：

```text
modules/amc_mta/outputs/attribution/
```

正式保留五份 CSV，其余生成输出由 `.gitignore` 排除。

## 运行业务测试

```bash
python3 -m unittest discover -s modules/amc_mta/tests -p 'test*.py'
```

当前基线为 100 项通过。

## 验证 BMad 配置

```bash
python3 -m unittest discover -s _bmad/scripts/tests -p 'test*.py'
```

当前基线为 1 项通过。`_bmad/config.toml` 和 `_bmad/config.user.toml`
由安装器管理，不应直接修改；持久覆盖应写入 `_bmad/custom/`。

## 工具代码检查

工作区全量审计使用以下类别的只读检查：

```text
Python: ast.parse 全部 .py
JavaScript: node --check 全部 .js
Bash: bash -n story-automator
Markdown: 项目自有文档本地链接存在性
JSON/TOML: 实际配置和数据文件解析
```

已知工具层限制：

- `.agents/skills/bmad-module-builder/scripts/tests/test-scaffold-standalone-module.py`
  有 1 项插件命名断言失败；
- `.agents/skills/bmad-workflow-builder/scripts/tests/test_memlog.py`
  依赖未声明的 `pytest`。

这两项应在维护安装技能时单独处理，不应与 AMC MTA 回归测试合并。

## 修改原则

- 新增、移动或归档文件先遵循[工作区文件位置管理](workspace-file-management.md)。
- 当前业务能力只在 `modules/amc_mta` 中扩展。
- 输入字段、五段键或输出列变化时，同步更新代码、样例、测试和模块契约。
- `docs/research` 的外部原件不作为运行输入。
- `design-artifacts` 与已完成规格保持历史原文，新增状态说明而不是改写过去意图。
- `.agents` 与 `_bmad` 视为安装型工具资产；修改前先确认问题属于本项目定制还是
  上游安装包。
- 不恢复已删除的旧 `modules/mta`。

## 当前没有的工程流程

仓库没有 CI/CD、容器、部署清单、数据库迁移、Web 服务或包发布配置。因此不存在
可记录的生产部署步骤；后续进入生产化时应先建立依赖锁定与 CI 测试门禁。
