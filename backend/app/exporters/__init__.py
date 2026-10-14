"""导出器 —— 纯粹的 `IR → 文件` 转换。

AGENTS.md 硬规则:**渲染器和导出器里不许有模型调用。**
这条保证教案和课件不会互相矛盾(它们来自同一份 IR),也让导出能单元测试。
"""

from app.exporters.docx import exam_paper_to_docx, lesson_plan_to_docx
from app.exporters.pptx import slide_deck_to_pptx

__all__ = ["slide_deck_to_pptx", "lesson_plan_to_docx", "exam_paper_to_docx"]
