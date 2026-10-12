"""ModelRouter —— 所有模型调用的唯一入口。

硬规则(AGENTS.md 第 3 节):禁止在业务代码里硬编码模型名。
换模型只改 config/models.yaml。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from app.config import settings

Task = Literal[
    "intent", "outline", "section", "question", "verify_answer",
    "mermaid", "vision", "embed", "image", "tts",
]


class TaskConfig(BaseModel):
    """某个任务该用哪个 provider / 模型 / 温度。"""

    provider: str
    model: str | None = None
    tier: str | None = None
    temperature: float = 0.0
    voice: str | None = None


class ModelRouter:
    """把「任务名」映射到「模型配置」。**所有模型调用的唯一入口。**"""

    def __init__(self, tasks: dict[str, TaskConfig]) -> None:
        """存下任务名 → 配置的映射。"""

        self._tasks = tasks

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ModelRouter":
        """从 config/models.yaml 读配置。换模型只改那个文件。"""

        data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls({k: TaskConfig(**v) for k, v in data["tasks"].items()})


    def for_task(self, task: str) -> TaskConfig:
        """取某个任务的配置。任务名没定义就报错 —— 不做默认兜底,免得悄悄用错模型。"""

        if task not in self._tasks:
            raise KeyError(f"config/models.yaml 未定义任务:{task}")
        return self._tasks[task]

    @property
    def tasks(self) -> list[str]:
        """已配置的任务名,用来检查拼写。"""

        return sorted(self._tasks)


@lru_cache
def get_router() -> ModelRouter:
    """进程级单例。配置改了要重启(暂不支持热加载)。"""

    return ModelRouter.from_yaml(settings.models_config_path)
