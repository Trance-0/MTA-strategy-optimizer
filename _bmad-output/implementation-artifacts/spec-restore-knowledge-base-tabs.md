---
title: '恢复 Knowledge Base 五标签'
type: 'bugfix'
created: '2026-09-04'
status: 'done'
baseline_commit: '238e3faf0ae9ca807db95c4b5b4858a355419d8a'
context:
  - docs/en/dashboard/views.md
  - docs/en/dashboard/deployment.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前部署只显示 Knowledge status 与 Ontology Review，遗漏了用户原先接受的 Touchpoint vocabulary、Rules、Entities、Data sources 四个标签。首次删除发生在旧主线 `a035383`，而 Gate D 从该主线重建时没有恢复 Gate A 的五标签设计。

**Approach:** 在当前 Gate D canonical 读取和校验逻辑之上恢复四个 snapshot-derived operational reference 标签，并让五个标签都使用现有深链与 lazy resource 机制。旧四页明确描述为当前 Dashboard 数据的展示层参考，而非 backend-owned ontology。

## Boundaries & Constraints

**Always:** 保留 canonical Ontology Review 的恰好五项、逐字节校验、失败关闭、超时/重试、键盘和窄屏合同；保留现有 Docker hotfix 与 0.9.43 发布记录；旧四页只读取现有 snapshot/resource 字段，不计算归因或预算结论；文档先于代码更新；所有标签支持 ArrowLeft、ArrowRight、Home、End。

**Ask First:** 改变 canonical fixture 字节、R5 语义或 verdict；改变旧四页展示字段的业务含义；引入新的后端资源类别而非复用现有只读资源；扩大到其他 Dashboard 页面。

**Never:** 修改 `modules/`、算法、模型或优化器；把旧四页称为 backend-owned ontology；调用 Review API、聊天或外部服务；回退整个 PR #4；提交生成的 public/dist/site 文件；提交或推送本分支。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Vocabulary | `attributionResults` 已加载 | 展示五段 key 定义和当前 touchpoint | 资源失败沿用 Dashboard 错误态，不伪造行 |
| Rules | `strategyRequest` 有/无 capacity rules | 展示 reliability、outcomes、capacity rules | 缺少 rules 时显示原说明，不报成 ontology 失败 |
| Entities | `strategyRequest` 与 `candidatePool` | 展示 Campaign Group、Campaign 和候选计数 | 空数组使用原 empty copy |
| Data sources | shell mode/source | 展示当前来源和静态 artifact 说明 | 缺值显示 `--` |
| Ontology Review | 受校验的 canonical bundle | 保留五个 cases 与所有既定状态 | 任一校验失败则不显示 verdict |

</frozen-after-approval>

## Code Map

- `docs/en/dashboard/views.md` -- 五标签语义、来源边界、状态和可访问性合同。
- `dashboard/src/views/KnowledgeBase.vue` -- 合并旧四页派生展示与当前 canonical review。
- `dashboard/src/pages.js` -- 五个 subsection 深链和 lazy resource 声明。
- `backend/repository/snapshot.py` -- 现有 `budget` 资源的只读 `candidatePool` 投影。
- `dashboard/tests/dashboard.test.js`、`dashboard/tests/ontology_review_fixtures.test.js`、`backend/tests/test_snapshot.py` -- UI、canonical 与资源回归。
- `VERSION`、`docs/version/0.9.43.md`、`docs/version/index.md`、`docs/worklog/YayuYu.md` -- hotfix 发布记录。

## Tasks & Acceptance

**Execution:**
- [x] `docs/en/dashboard/views.md` -- 删除“previous vocabulary removed”合同，定义 operational reference 四标签加 canonical 第五标签。
- [x] `dashboard/src/views/KnowledgeBase.vue` -- 从历史已验证实现恢复四页的 imports、computed rows 和 panels，并与当前 route-controlled canonical 状态合并。
- [x] `dashboard/src/pages.js` -- 默认 vocabulary，声明 vocabulary/rules/entities/sources/ontology-review 及最小资源集合。
- [x] `backend/repository/snapshot.py` -- 仅把 `candidatePool` 加入既有 `budget` resource；不改变 loader、模型或算法。
- [x] Dashboard/backend tests -- 固定五标签、深链资源、旧四页关键内容、candidatePool 投影和 canonical 五 cases。
- [x] 0.9.43 记录 -- 将恢复内容与 Docker 接线合并为同一 hotfix 说明，保持索引和工作日志一致。

**Acceptance Criteria:**
- Given Knowledge Base 已打开，when 用户切换标签或使用四种键盘键，then 恰好五个标签均可访问且对应深链稳定。
- Given 当前 snapshot 数据，when 打开旧四标签，then 原 vocabulary、rules、entities、sources 信息恢复，且页面明确说明它们是 operational reference。
- Given canonical bundle，when 打开 Ontology Review，then 五 cases、身份、policy、verdict、证据、限制和下一步与 Gate D 一致。
- Given 最终 diff，when 审计路径，then `modules/`、算法、模型和优化器为零变更，生成物未跟踪。

## Spec Change Log

- 2026-09-04: Approved implementation completed from baseline `238e3faf0ae9ca807db95c4b5b4858a355419d8a`; restored four route-controlled snapshot references, retained the canonical fifth tab, extended the existing budget projection, and updated release records.
- 2026-09-04 review patch: added partial-snapshot guards, truthful database/file/unknown empty states, file-mode provenance wording, keyboard resource preloading before route focus, narrow-screen tab scrolling, and targeted regression assertions; resource and algorithm boundaries remain unchanged.

## Design Notes

不要直接恢复 Gate A 的本地 `tab` 状态。当前应用以 `pages.js` subsection 驱动深链和按需加载，因此五标签应由 `props.section`/`navigate` 控制。旧四页复用 `useDashboard()`，Ontology Review 继续只通过 `ontologyReviewFixtures.js` 读取 canonical assets；两个来源在文案和加载路径上保持分离。

## Verification

**Commands:**
- `npm test --prefix dashboard` -- 五标签与全部 96/96 Dashboard 测试通过。
- `uv run --extra backend python -m unittest backend.tests.test_snapshot` -- `candidatePool` 只读资源投影通过。
- `npm run build --prefix dashboard` 与 `npm run build:static --prefix dashboard` -- normal/static 均含已验证 canonical bundle。
- `npm run build --prefix docs`、`node script/build_pages_site.mjs` -- 文档与最终 Pages 组装通过。
- `git diff --check` 与路径审计 -- 无算法目录或生成物变化。
- `docker build -f deploy/docker/Dockerfile.dashboard .` -- Docker daemon 可用时通过；不可用则保留明确环境性缺口。

**Results (2026-09-04):**
- `npm test --prefix dashboard`: 96/96 passed after review patches.
- `uv run --isolated --python C:\Users\YYY\AppData\Local\Programs\Python\Python314\python.exe --extra backend python -m unittest backend.tests.test_snapshot`: 10/10 passed.
- `npm run build --prefix dashboard`: passed; five published canonical fixtures verified.
- Static equivalent sequence passed: isolated snapshot export, `vite build --mode static`, and five-fixture output verification. The wrapper `npm run build:static --prefix dashboard` remains blocked before project execution because Windows Application Control rejects `_socket` in uv's default Python 3.12 runtime.
- `npm run build --prefix docs`: passed after lockfile installation. `node script/build_pages_site.mjs`: passed, assembling 761 files.
- `git diff --check`: passed. `git diff <baseline> -- modules`: empty. No generated build artifact is tracked.
- Docker image build was not repeated because Docker Desktop remains unavailable; the pre-existing 0.9.43 release note retains that environment gap.
## Suggested Review Order

**UI boundary**

- Five tabs share route control while canonical loading stays isolated.
  [`KnowledgeBase.vue:31`](../../dashboard/src/views/KnowledgeBase.vue#L31)

- Keyboard navigation preloads target resources before moving focus.
  [`KnowledgeBase.vue:312`](../../dashboard/src/views/KnowledgeBase.vue#L312)

- Caption separates snapshot references from the canonical fixture source.
  [`KnowledgeBase.vue:332`](../../dashboard/src/views/KnowledgeBase.vue#L332)

**Route and data boundary**

- Route metadata declares exact deep links and lazy resource sets.
  [`pages.js:82`](../../dashboard/src/pages.js#L82)

- The server keeps resource names behind a fixed allow-list.
  [`snapshot.py:156`](../../backend/repository/snapshot.py#L156)

- Budget projects candidate counts without creating another resource category.
  [`snapshot.py:166`](../../backend/repository/snapshot.py#L166)

**Responsive behavior**

- Narrow tabs scroll horizontally without shrinking their labels.
  [`style.css:2586`](../../dashboard/src/style.css#L2586)

**Regression coverage**

- Dashboard tests cover guards, preload ordering, and responsive CSS.
  [`dashboard.test.js:644`](../../dashboard/tests/dashboard.test.js#L644)

- Backend tests pin the budget resource projection shape.
  [`test_snapshot.py:145`](../../backend/tests/test_snapshot.py#L145)

**Docker boundary**

- The root importer is copied before Dashboard prebuild executes.
  [`Dockerfile.dashboard:20`](../../deploy/docker/Dockerfile.dashboard#L20)

**Documentation and release**

- View documentation distinguishes four references from canonical review.
  [`views.md:13`](../../docs/en/dashboard/views.md#L13)

- The hotfix combines tab restoration with Docker build wiring.
  [`0.9.43.md:8`](../../docs/version/0.9.43.md#L8)
