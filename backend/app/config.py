"""应用配置。

═══════════════════════════════════════════════════════════════════
配置从哪来,谁优先
═══════════════════════════════════════════════════════════════════
    显式传参 > 环境变量(os.environ)> env.yaml > secrets 文件

**环境变量优先于 env.yaml** 是刻意设计的(见 AGENTS.md 第 6 节):

  · 本地开发 —— 把 key 写在 `env.yaml` 里,方便、且已被 git 忽略
  · 生产环境 —— 什么都不带,由部署平台注入环境变量

同一份代码两种环境都能跑,部署时不需要把 yaml 传上去。
如果反过来的话,一个提交进仓库的 yaml 就能悄悄覆盖生产配置 —— 那很危险。

NFR-03:密钥只在此处读取,禁止写入日志或响应。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

#: 默认的本地配置文件位置(相对 backend/ 目录)
DEFAULT_YAML_FILE = "env.yaml"


def config_file() -> Path:
    """当前离线配置文件的路径。

    可用环境变量 `APP_CONFIG_FILE` 覆盖 —— 主要是给测试用的,
    这样测试不必依赖仓库里真实存在的 env.yaml。
    """
    return Path(os.environ.get("APP_CONFIG_FILE", DEFAULT_YAML_FILE))


class Settings(BaseSettings):
    """应用配置。字段名对应 env.yaml 里的键(或同名大写的环境变量)。"""

    # 注意:这里**不写** yaml_file。
    # 写了但源是条件添加的,pydantic-settings 会报
    # "Config key `yaml_file` ... will be ignored" 的警告。
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/comp5241"
    redis_url: str = "redis://localhost:6379"

    # 模型凭据:只在此处读取,禁止写入日志或响应
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    #: 文本生成用的模型名。当前 DeepSeek 只有两个模型:
    #:   deepseek-flash   —— DeepSeek-V4.1-Flash,1M 上下文,工具调用 + **图像理解**
    #:   deepseek-v4-pro  —— 更强,但不支持图像理解,价格贵约 4.5 倍
    #: 旧的 deepseek-chat / deepseek-reasoner 已不在模型表里。
    #: 用 `python -m app.check_deepseek` 可以列出你这个 key 实际能用的模型。
    deepseek_model: str = "deepseek-flash"
    #: 读图用的多模态模型。Flash 同时支持文字和图像,所以默认同上;
    #: 单独留一个字段是为了以后能拆开(比如文本换 Pro、读图仍用 Flash)。
    deepseek_vision_model: str = "deepseek-flash"
    #: 思考模式。**默认关闭**,两个原因:
    #:   1. 开启后 `temperature` 不生效(服务端静默忽略),而各任务的
    #:      temperature 是 config/models.yaml 里明确配的
    #:   2. 更贵更慢 —— agent 循环每轮都要多想一遍
    #: **默认关闭**:实测同一次 L1 生成,关闭后输出 token 降到 36%、成本降 41%。
    #: 打开是安全的 —— reasoning_content 的回传已经在 agent.py 里处理好了,
    #: 漏了那个会直接 HTTP 400。
    deepseek_thinking: bool = False

    gemini_api_key: str = ""
    siliconflow_api_key: str = ""

    models_config_path: str = "config/models.yaml"
    upload_dir: str = "var/uploads"

    cors_origins: list[str] = [
        # 开发时两种写法都常见,少一个都会在浏览器里表现为「莫名其妙的跨域失败」。
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """决定「谁覆盖谁」。返回的元组里,**越靠前优先级越高**。

        注意 `dotenv_settings` 被故意丢弃 —— 我们不用 `.env`,用 `env.yaml`。
        """
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,   # 1. 代码里显式传的
            env_settings,    # 2. os.environ(生产环境走这条)
        ]

        # 3. env.yaml —— 只在文件存在时才加进来。
        #    不存在就静默跳过,而不是报错:生产环境本来就不该有这个文件。
        yaml_path = config_file()
        if yaml_path.exists():
            sources.append(YamlConfigSettingsSource(settings_cls, yaml_file=yaml_path))

        sources.append(file_secret_settings)  # 4. Docker secrets 等
        return tuple(sources)


@lru_cache
def get_settings() -> Settings:
    """进程级单例。测试里想换配置就直接构造 Settings(),别用这个。"""

    return Settings()


settings = get_settings()
