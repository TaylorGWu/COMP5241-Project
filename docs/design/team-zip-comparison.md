# 组员最终 ZIP 对照审查记录

审查日期：2026-11-09。对象：组员最终包 `5241 project v3.zip`。

- 原始 ZIP：`5241 project v3.zip`，386 MB，39,633 个文件
- SHA-256：`3e5253e5b83cf6fced3b48eff2f2b0e75e9467ad69394b0948697a3d662f6a4f`
- 解压位置：仓库内 `.zip-review/B`（已加入 `.git/info/exclude`，不进 Git）
- 对照基线 A：分支 `codex/student-admin-portals`，提交 `98e238c`

## 0. 包安全检查

| 检查项 | 结果 |
| --- | --- |
| 路径穿越 / 绝对路径 | 无 |
| 符号链接 | 无 |
| 硬编码密钥 | 无。`backend/env.yaml` 为模板，`deepseek_api_key` 等均为空字符串 |
| 夹带数据库 | **有**：`backend/.local/teacher-workspace.db`（2.5 MB）。未使用，未覆盖 A 的数据库 |
| 夹带依赖 / 构建缓存 | 有：`frontend/node_modules`（23,576 项）、`.venv`（Windows 版，`Scripts/`）、`frontend/.next` |
| 包内说明文件 | `START_HERE.zh-CN.md`、`HANDOFF_MANIFEST.json` 等仅阅读，未执行任何包内脚本 |

未执行包内任何脚本。解压时排除了 `node_modules`、`.venv`、`.next`。

## 1. 总体结论

两份代码是同一支线的两个后续方向，**不是新旧关系**。

- **教师端完全一致。** `edit.py`、`edit_planning.py`、`patches.py`、`questions.py`、`illustrations.py`、
  `pipeline.py`、`mermaid_assets.py`、`exporters/pptx.py`、`exporters/docx.py`、`SlideActions.tsx`、
  `test_quiz_format.py`、`test_question_sources.py` 在两边逐字节相同。交接文档要求保留的七项教师端修复
  （插入后 AI 改对页、拒绝不改正文、无双重字母编号、"Pick one" 不变成选项、导出读取已保存内容、
  插图失败不拖垮整章、结构图用 Mermaid）**A 和 B 都在**。
- 分歧集中在**学生端、管理员端、发布（publication）层、以及前端外壳与视觉层**。
- 两边测试都是绿的：A `469 passed`，B `459 passed`。所以 B 不是坏代码，是一套自洽的替代实现。

因此整合方式定为：**以 A 为主体，按功能把 B 的优势移植到 A 的模型上**，不整包替换。
理由见 §4；A 在权限、数据不可变性、审计、UI 上更严格且更完整，B 的浮层文件与 A 互不兼容。

## 2. 逐项对照

### 2.1 必须保留 A（B 覆盖会造成构建失败、权限退化或视觉回退）

| 功能或模块 | A 的实现 | B 的实现 | 建议采用 | 理由与风险 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| 前端外壳样式导入 | `app/layout.tsx` 导入 `portals.css` + `workspace-theme.css` | 导入 `student.css` + `admin.css` | **保留 A** | A 无 `student.css/admin.css`，B 无 `portals.css/workspace-theme.css`。覆盖即 Next 构建失败；删导入则丢失暖白色板与 `.chapter-workspace-page` 字体 | `npx tsc --noEmit`、`npm run build`、`export-target.cjs` |
| 首页主 CTA | `PublicHome.tsx` 有真实 `home-primary-action` 链接（按角色跳转） | **删除**该 CTA，仅留正文与 assurance | **保留 A** | 直接违反 `ui-style-guide.md`「保留首页 JSX，CTA 不是装饰按钮」；B 同包把 `home-landing.cjs` 中对应断言一并删掉 | `home-landing.cjs`（断言 hero 主按钮数量为 1） |
| 首页视觉 | 暖白 `#f7f6f2`、居中 72px、深色主按钮 | 旧版：白底、双栏、60px 渐变裁切文字、蓝色按钮 | **保留 A** | B 为 Kipwise 之前的概念；且 B 的深色块删掉 `--color-ink/body/muted` 覆盖，深色模式对比度会退化 | `home-landing.cjs` 三语言 × 1440/768/390/320 + 深色 |
| `AccountPages.tsx` | 导出 `ApplicationQueue`（含 abort 控制、搜索） | 无 `ApplicationQueue`，导出 `AdminAccountPage`/`StudentAccountPage` | **保留 A** | `portals/AdminPortal.tsx` 导入 `ApplicationQueue`，覆盖即构建失败；B 版还会重新引入卸载后 setState | `tsc`、门户测试 |
| 认证服务 | `services/auth.py` 调用 `portal_store.migrate()` | 无 portal 迁移 | **保留 A** | 覆盖后 `portal_*` 表不再创建，学生端整体失效 | `test_portals.py` 迁移用例 |
| 学生路由加固 | `routes/auth.py` 把 `/api/student/` 列入 `no-store` 与 16 KB 请求体上限 | 未列入 | **保留 A** | B 缺这层，学生写请求可被缓存且无体积上限 | 安全检查 + `test_portals.py` |
| 发布链路 | `publication.publish()`：校验课程所有者、至少一节 ready 且有幻灯片、写入冻结快照 | `COURSE_WORKSPACE.publish()` 只查 `status=='ready'` 且 `package is not None` | **保留 A** | A 会拒绝空发布；B 允许发布空 deck，且**不写 `portal_publications`**，学生端看不到新发布课程 | `test_teacher_courses_api.py`、`test_portals.py::test_empty_publication_is_rejected...` |
| 邀请码 | `secrets.token_urlsafe(18)` + 写入 `portal_invites` | 顺序号 `invite-{course_id}-{n}`，且**不写 `portal_invites`** | **保留 A** | B 的码可猜且无法兑换（A 的 `/join` 读 `portal_invites`）。这是全对比中最明显的安全回退 | `test_portals.py::test_invite_and_private_snapshot_asset_boundaries` |
| `/api/demo/analytics` | 读快照 + `student_learning.state()` | 导入 `_course_summary`、`_ready_chapters`、`StudentLearningStore` | **保留 A** | B 引用的三个符号在 A 中都不存在，覆盖即 `ImportError` → 500 | 后端测试 + 真接口调用 |
| 停用课程模型 | `portal_moderation` 单行＝停用，恢复＝删行，学生/教师/发布统一读它 | `payload["status"]="draft"` 改写 + 追加式日志 | **保留 A** | 两套语义并存会让彼此的停用互相不可见。B 的 `take_down` 破坏已发布状态，`reinstate` **不恢复**（已复现，见 §3） | `test_portals.py::test_admin_suspends_and_restores_course...` |
| 用户管理不变量 | 事务内重查管理员、禁止自我锁死、保护最后一个管理员、改角色删会话、写审计 | 分开两个端点；最后管理员仅防自我降级；**用户变更不写审计**；提升为 instructor 直接 `approved` | **保留 A** | A 更严格。B 把学生提为教师时直接 `approved`，绕过资格审核 | `test_portals.py::test_admin_suspends_and_restores_course_and_protects_accounts` |
| 管理员分析 | 指标卡/角色环图/课程状态堆叠/选课条形图，全部可下钻到精确筛选列表 | 4 个静态卡片，仅切 tab，无筛选下钻 | **保留 A** | 交接文档明确「统计与图例可以跳到相应列表，不是静态装饰」 | `portals.test.mjs` 下钻用例 + 手工点击 |
| 管理员 API 鉴权 | 每个路由 `await admin_user(request)`，写入事务内再查一次角色 | 路由级 `require_role(Role.admin)`，服务层无检查 | 保留 A（B 也可接受） | 两者都正确；A 多一层纵深防御 | 越权用例：学生/教师访问 `/api/admin/*` 应 403 |

### 2.2 值得从 B 移植（B 更优）

| 功能或模块 | A 的实现 | B 的实现 | 建议采用 | 理由与风险 | 验证方式 |
| --- | --- | --- | --- | --- | --- |
| 答错后回看相关页面 | 只给解析文本 | 按 `objectiveIds` 交集找一页（排除 `teaching_role=='check_understanding'`），返回 `reviewSlideId` | **移植** | 唯一有教学意义的独有功能；A 的 IR 已有 `objective_ids`/`teaching_role`，可服务端计算，不需要把答案相关字段下发前端 | 新增后端用例 + 手工答错后跳转 |
| 推荐理由分类 | 仅词重叠，已选课程一律排除，理由是一句模板 | 按续学(+8)/目标词/初学匹配/时长排序，返回 `resume`/`goal`/`time`/`start` | **移植（改造后）** | 更贴合「可解释的下一步」。B 用 `background=="new"` 等类别语义，A 的 `background` 是自由文本，需改用 A 的字段语义 | 推荐用例 + 三语言文案 |
| 学习时长预算 | 无 | `weekly_minutes`（15–1200）参与 `time` 理由 | **移植（需 v4 迁移）** | 支撑 `time` 理由。A 的 `portal_profiles` 需加列，并补 UI 输入 | 迁移用例（备份 + 幂等）+ 手工 |
| 学生文案准确性 | 「学习端正独立开发」等旧描述 | 「浏览已发布课程、完成练习并延续进度」 | **移植** | A 已有可用学生门户，旧文案与实际不符；`studentRegisterBody` 仍在注册页渲染 | 三语言页面检查 |
| 下一章导航 | 无 | 练习页可跳下一章 | 可选 | 小改动，体验加分 | 手工 |
| 课程摘要 | 课程详情不含章节摘要 | 含 `summary` | 可选 | 低风险 | 手工 |
| 移动端课件渲染 | 单 `SlideFrame` | 手机用 `<article>` 版式 | 可选 | A 已过 320px 检查，优先级低 | 320px 手工 |

### 2.3 明确不采用

| 功能或模块 | B 的问题 | 决定 |
| --- | --- | --- |
| `AI 审计日志` | `_migrate()` 每次请求执行，并在表为空时**伪造**最多 15 条记录：模型写死 `"deepseek-chat"`、`duration_ms = 1450 + i*137 % 2500`、`estimated_tokens` 与时间戳均为编造，归属到某个真实教师 | **不采用**。违反「不许硬编码模型名」「不增加假数据」。若要保留该能力，须重写为由生成流水线真实写入 |
| `POST /admin/ai/audit-logs` | 由调用方自报模型/耗时/令牌，无生成钩子写入，审计不可信 | **不采用** |
| B 的 `admin_governance.py` | 与 A 的 `portal_moderation` 语义冲突；`_migrate()` 每请求执行；停用改写 payload | **不采用** |
| B 的学生/管理员组件与 `student.css`/`admin.css` | 与 `PortalShell`/`portals.css` 双入口；且是旧视觉 | **不采用** |
| B 的 `demo.py`、`services/auth.py`、`routes/auth.py`、`layout.tsx`、`homepage.css`、`PublicHome.tsx`、`AccountPages.tsx` | 见 §2.1 | **不采用** |

## 3. 已复现的 B 缺陷

1. **`reinstate` 不恢复课程。** 用 B 的 `AdminGovernanceStore` 在临时库复现：
   `published` → `take_down` 后 `draft` → `reinstate` 后仍 `draft`（仅 `is_course_taken_down` 变回
   `False`）。B 自己的 `test_admin.py` 也写进了「恢复后需教师重新发布」这一语义。
2. **课程列表字段读错命名。** `list_courses` 读 `courseCode`/`chapterIds`/`durationMin`，但
   `payload_json` 存的是 snake_case，管理员课程表恒显示空课程号与 `0 ch.`。
3. **管理员 UI 的 reinstate 按钮失效。** `setModModal(course)` 后立刻 `submitModeration("reinstate")`，
   命中 `if (!modModal) return;` 的旧闭包，实际打开的是「Take Down Course」弹窗。
4. **`answer` 未绑定题面版本。** B 直接按实时 `question["answer"]` 判分；教师若在学生作答期间改题，
   学生会按从未见过的题面被判分。A 用 `questionRevision` HMAC + 409 拦截。
5. **B 无选课实体。** 任何学生角色账号都能直接读任意已发布章节并作答；A 要求先选课（403）。

## 4. 为什么以 A 为主体

1. 教师端两边逐字节相同，以 A 为主体不损失任何教师端修复。
2. A 的内容不可变性更强：发布写入冻结快照，学生按快照读取，教师改稿不会中途泄漏；B 直接读实时行。
3. A 的权限更严：选课门禁、停用过滤、`/api/student/` 请求加固、管理员写入事务内二次鉴权。
4. A 的存储更完整：`portal_publications`/`enrollments`/`invites`/`moderation`/`audit`，
   以及带 `question_hash`、`correct_option`、`UNIQUE(user_id,submission_id)` 的不可变作答记录。
5. A 携带已确认的 Kipwise 视觉和首页 CTA；B 是之前的概念。
6. A 的测试更多且更针对边界（469 vs 459，A 覆盖空发布、过期题面、越权资源、迁移备份）。

## 5. 整合后必须重跑的验证

整合前的通过结果不能沿用。

| 范围 | 链路 |
| --- | --- |
| 教师 | 创建课程 → 新增章节 → 生成（离线夹具）→ 人工编辑 → 审核 → 发布 |
| AI 修改 | 插入幻灯片后选中目标页 → 提意见 → 接受/拒绝；只改目标页；拒绝不改正文 |
| 导出 | 改稿后导出 PPTX / DOCX，检查文字与图片；不宣称原生 PDF |
| 学生 | 加入课程 → 阅读 → 答错 → 回看相关页 → 答对 → 刷新后进度保留 |
| 管理员 | 审核教师 → 改角色/停用 → 下架/恢复课程 → 查看审计（含操作人） |
| 三端联动 | 教师发布后学生可见；管理员下架后学生 404；恢复后学生可见 |
| 权限 | 学生/教师访问 `/api/admin/*` 与未选课章节均被后端拒绝，不靠前端隐藏 |
| UI | 顶部导航、侧栏、账户菜单、设置、编辑器；浅色/深色、三语言、320px、键盘焦点 |

命令：

```bash
cd backend && ../.venv/bin/python -m pytest -q
cd frontend && npx tsc --noEmit && npm run lint
cd frontend && node --experimental-strip-types --test tests/portals.test.mjs
```

UI 脚本在 `tools/ui-verify/`，需要已启动的前端和 Playwright。
