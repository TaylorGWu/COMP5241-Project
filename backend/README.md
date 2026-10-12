# backend — FastAPI 后端

结构与设计规格 `docs/design/course-generation-design.md` 对应。

## 运行

```bash
cd backend
cp env.yaml.example env.yaml   # 填入密钥(env.yaml 已被 git 忽略)
../.venv/bin/pip install -r requirements.txt
../.venv/bin/uvicorn app.main:app --reload
```

健康检查:`GET http://127.0.0.1:8000/api/health`

## 跑起来看看(不需要 API key)

```bash
cd backend
../.venv/bin/python -m app.demo_pipeline
```

这是一条完整跑通的 L1 流水线:六段进度 → 三个 SectionAgent 并发工作 →
产出 IR → 跑交叉引用校验。**阶段 1 会真读一份讲义,并用它的 chunk 做检索。**

单独看材料摄取:

```bash
cd backend
../.venv/bin/python -m app.demo_ingest      # 现场造 7 种材料并逐个摄取
```

它用**规则版假模型**替换了真模型,用**内存假实现**替换了检索和渲染。
换成真实现时,`agent.py` 和 `pipeline.py` 一行都不用改 —— 这就是依赖注入的意义。

## 测试

```bash
cd backend
../.venv/bin/pytest          # 32 个测试
```

测试断言的是**工具调用序列**,不是模型输出的文本 ——
文本每次都不同,断言它等于没断言。

## 目录

| 路径 | 对应规格章节 |
| --- | --- |
| `app/schemas/ir.py` | §5.1 IR 结构 + §6.4 校验规则(27 个模型) |
| `app/services/agent.py` | §6.2 / §7 **agent 循环**(终止工具、轮数上限、工具序列留痕) |
| `app/services/tools.py` | §6.2 SectionAgent 工具集 · §7.1 编辑 Agent 工具集 |
| `app/services/pipeline.py` | §6.1 **六阶段流水线**(进度、并发、失败隔离) |
| `app/services/ingest.py` | §6.1 **阶段 1 材料摄取**(magic bytes 探测 · 扫描件转 OCR · 分块保页码) |
| `app/demo_ingest.py` | 可运行演示:7 种材料 + 摄取报告 |
| `app/llm/client.py` | 模型客户端(含离线假模型) |
| `app/llm/router.py` | §11.4 ModelRouter |
| `app/api/deps.py` | §5.5 权限矩阵(后端强制) |
| `app/demo_pipeline.py` | 可运行演示(假模型) |
| `app/workers/` | 异步作业 + SSE(待实现) |
| `config/models.yaml` | §11.4 模型配置 |

## 三条必须遵守的硬规则(见 AGENTS.md)

1. AI 只产出 IR,不产出 HTML / pptx —— 渲染与导出是纯转换
2. 模型调用一律经 `ModelRouter`,禁止硬编码模型名
3. 只有 `POST /api/patches/{id}/apply` 会修改 `artifacts` 内容


---

## 材料摄取支持什么

**不靠扩展名判断,靠文件头 + 内容探测。** 因为同一个 `.pdf` 可能是两种完全不同的东西。

| 上传的东西 | 探测结果 | 怎么处理 |
| --- | --- | --- |
| 有文字层的 PDF | `text_pdf` | PyMuPDF 直接抽文字 + 页码 |
| **扫描版 PDF** | `scanned_pdf` | 渲染成图 → **转 OCR** |
| PPTX / DOCX | `pptx` / `docx` | 抽文字 + 表格 + 备注 |
| Markdown / TXT | `text` | 直接读 |
| 图片(拍的书页、截图) | `image` | **走 OCR** |
| 其它 | `unsupported` | 拒绝,并说明支持哪些格式 |

**每份材料都报告抽到多少字**,而不是笼统的「解析成功」:

```
✅ 讲义.pdf        text_pdf · 2 页 · 112 字
⚠️  扫描版讲义.pdf  scanned_pdf · 1 页 · 58 字 · 已 OCR   ← 建议抽查识别准确性
❌ 报表.xlsx       unsupported · 0 字                     ← 不支持的格式
```

抽到 0 字一定标为失败 —— 静默成功会让教师以为是模型不行,而实际是文件没读到。

**OCR 是可替换的:** `IngestDeps(ocr_image=...)`。demo 用假实现,
生产接 DeepSeek Flash(demo 不需要 API key 就是因为这个)。
