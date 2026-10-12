"""配置加载测试 —— 锁定「环境变量 > env.yaml」这条约定。

这条约定是**刻意**的(见 AGENTS.md 第 6 节):生产环境走环境变量,
`env.yaml` 只作本地兜底。

如果有人把它反过来,一个提交进仓库的 yaml 就能悄悄覆盖生产配置。
这个测试就是拦住那种改动 —— 它保护的不是功能,是一个安全属性。
"""

from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture
def yaml_config(tmp_path, monkeypatch):
    """准备一个临时的 env.yaml,并让 Settings 去读它。"""
    path = tmp_path / "env.yaml"
    path.write_text(
        "deepseek_api_key: from-yaml\ndeepseek_model: yaml-model\n", encoding="utf-8"
    )
    monkeypatch.setenv("APP_CONFIG_FILE", str(path))
    # 清掉可能存在的真实环境变量,避免污染断言
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    return path


def test_yaml_is_read(yaml_config):
    s = Settings()
    assert s.deepseek_api_key == "from-yaml"
    assert s.deepseek_model == "yaml-model"


def test_environment_variable_overrides_yaml(yaml_config, monkeypatch):
    """同一项在两处都有时,环境变量必须赢。"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    s = Settings()
    assert s.deepseek_api_key == "from-env"
    # 没被环境变量覆盖的那项仍然来自 yaml
    assert s.deepseek_model == "yaml-model"


def test_yaml_absent_falls_back_to_defaults(tmp_path, monkeypatch):
    """没有 env.yaml 也不能崩 —— 生产环境本来就不该有它。"""
    monkeypatch.setenv("APP_CONFIG_FILE", str(tmp_path / "definitely-not-here.yaml"))
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    s = Settings()
    assert s.deepseek_model == "deepseek-flash"
    assert s.deepseek_api_key == ""


def test_secrets_are_plain_strings_and_default_empty(monkeypatch, tmp_path):
    """默认值必须是空字符串,不能是任何看起来像真实密钥的东西。"""
    monkeypatch.setenv("APP_CONFIG_FILE", str(tmp_path / "none.yaml"))
    for k in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY", "SILICONFLOW_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    s = Settings()
    assert s.deepseek_api_key == ""
    assert s.gemini_api_key == ""
    assert s.siliconflow_api_key == ""
