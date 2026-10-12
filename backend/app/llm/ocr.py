"""用多模态模型做 OCR —— 替代 demo 里的假实现。

═══════════════════════════════════════════════════════════════════
为什么走多模态模型而不是传统 OCR
═══════════════════════════════════════════════════════════════════
传统 OCR(PaddleOCR / Tesseract)只认「字」;而讲义里的图往往还有:

    · 表格         → 需要还原结构
    · 流程图       → 需要说明它表达的关系
    · 公式         → 需要转成可读形式
    · 手写批注     → 传统 OCR 基本读不出来

多模态模型能一起处理。而且项目里已经在用 DeepSeek,不用再引一个依赖。

═══════════════════════════════════════════════════════════════════
接口
═══════════════════════════════════════════════════════════════════
`make_ocr(client, model)` 返回一个 `async (bytes) -> str`,正好是
`IngestDeps(ocr_image=...)` 要的签名。所以**换 OCR 不用改 ingest.py 一行**。

DeepSeek 的图片输入限制(见官方文档):
    · 格式:JPEG / PNG / GIF / WebP
    · 单图 ≤ 32 MiB(base64 / URL),单边 ≤ 8192px
    · 图片只能放在 `user` 消息里
"""

from __future__ import annotations

import base64

from app.llm.client import ChatClient

#: OCR 提示词。要求「原样输出」而不是「总结」——摄取的材料要保真。
OCR_PROMPT = """把这张图片里的内容**完整地转成文字**。

要求:
1. 逐字转录,不要概括、不要改写、不要补充你自己的知识。
2. 保持原有的层次:标题、列表、表格都按原结构输出。
3. 表格用 Markdown 表格;公式转成可读的纯文本形式。
4. 如果图里有流程图或结构图,在文字之后用一段话说明它表达的关系。
5. 图片模糊到无法辨认的部分,写 [无法辨认],不要猜。
6. 如果这张图里没有任何文字(纯装饰图),只回复:[无文字内容]

直接输出内容,不要加「以下是识别结果」之类的开场白。"""

#: 图片在消息里的 MIME。OCR 的输入主要是渲染出来的页面,统一按 PNG 处理。
_IMAGE_MIME = "image/png"


def make_ocr(client: ChatClient, model: str, *, temperature: float = 0.0):
    """造一个 OCR 函数:图片字节 → 文字。

    用法:
        deps = IngestDeps(ocr_image=make_ocr(chat_client, settings.deepseek_vision_model))
    """

    async def ocr(image_bytes: bytes) -> str:
        """把一张图交给多模态模型转录成文字。"""
        if not image_bytes:
            return ""

        b64 = base64.b64encode(image_bytes).decode("ascii")

        # 注意:图片必须放在 user 消息里 —— 放 system/assistant 会 400。
        reply = await client.complete(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{_IMAGE_MIME};base64,{b64}"},
                        },
                    ],
                }
            ],
            temperature=temperature,
        )

        text = reply.content.strip()
        if text == "[无文字内容]":
            return ""
        return text

    return ocr
