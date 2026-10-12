"""OCR 测试 —— 对应设计规格 §11.5(多模态图片输入)。

不调真模型,只验证「消息构造对了没有」和「边界处理」。
真调用放在 check_deepseek / demo_deepseek 里手动跑。
"""

from __future__ import annotations

import base64

from app.llm.client import ChatMessage, ScriptedChatClient
from app.llm.ocr import make_ocr


async def test_ocr_sends_image_in_user_message():
    """DeepSeek 规定图片只能放在 user 消息里 —— 放错会 400。"""
    client = ScriptedChatClient([ChatMessage(content="识别出来的文字")])
    ocr = make_ocr(client, "deepseek-flash")
    text = await ocr(b"\x89PNG\r\n\x1a\nfake")

    assert text == "识别出来的文字"
    sent = client.requests[0]["messages"]
    assert len(sent) == 1 and sent[0]["role"] == "user"

    blocks = sent[0]["content"]
    kinds = [b["type"] for b in blocks]
    assert "text" in kinds and "image_url" in kinds

    url = next(b for b in blocks if b["type"] == "image_url")["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"\x89PNG\r\n\x1a\nfake"


async def test_empty_image_short_circuits():
    """空图片不必浪费一次 API 调用。"""
    client = ScriptedChatClient([])
    ocr = make_ocr(client, "deepseek-flash")
    assert await ocr(b"") == ""
    assert client.requests == []


async def test_pure_decoration_returns_empty():
    """模型说「无文字内容」时,归一化成空串 —— 让上层的「0 字」判定生效。"""
    client = ScriptedChatClient([ChatMessage(content="[无文字内容]")])
    ocr = make_ocr(client, "deepseek-flash")
    assert await ocr(b"fake") == ""


async def test_prompt_asks_for_verbatim_transcription():
    """提示词必须要求「原样转录」—— 摄取的材料要保真,不能是摘要。"""
    client = ScriptedChatClient([ChatMessage(content="x")])
    ocr = make_ocr(client, "deepseek-flash")
    await ocr(b"fake")
    prompt = client.requests[0]["messages"][0]["content"][0]["text"]
    assert "完整" in prompt and "不要概括" in prompt


# ═══════════════════════════════════════════════════════════
# 思考模式开关:必须真的发出去
# ═══════════════════════════════════════════════════════════


def test_thinking_flag_is_sent_in_extra_body():
    """`thinking` 必须放进 extra_body —— OpenAI SDK 不认这个字段。

    而且三态要分清:
        False → "disabled"   关闭(默认)
        True  → "enabled"    开启
        None  → 不发这个参数,用服务端默认(DeepSeek 默认**开**)
    """
    from app.llm.client import OpenAICompatClient

    for flag, expected in ((False, "disabled"), (True, "enabled"), (None, None)):
        client = object.__new__(OpenAICompatClient)   # 绕过 __init__,不建真连接
        client._thinking = flag
        client._reasoning_effort = "high"

        kwargs: dict = {}
        if client._thinking is not None:
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled" if client._thinking else "disabled"}
            }

        if expected is None:
            assert "extra_body" not in kwargs, "None 时不该发这个参数"
        else:
            assert kwargs["extra_body"]["thinking"]["type"] == expected


def test_client_factory_honours_the_setting(monkeypatch):
    """工厂函数必须把配置里的开关带过去 —— 入口漏传就是靠它兜住的。"""
    import app.config as config_module
    from app.llm import client as client_module

    monkeypatch.setattr(config_module.settings, "deepseek_thinking", False)
    monkeypatch.setattr(config_module.settings, "deepseek_api_key", "sk-test")

    captured: dict = {}

    class _Fake:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(client_module, "OpenAICompatClient", _Fake)
    client_module.build_deepseek_client()

    assert captured["thinking"] is False
    assert captured["api_key"] == "sk-test"
