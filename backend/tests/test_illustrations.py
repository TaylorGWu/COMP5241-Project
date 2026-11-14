"""Image provider boundaries: real storage/validation, mocked external HTTP only."""
import base64
import io

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.llm.router import ModelRouter, TaskConfig
from app.services.illustrations import IllustrationError, IllustrationGenerator, read_illustration
from app.services.tools import SectionDeps, build_section_tools


def png():
    out = io.BytesIO()
    Image.new("RGB", (320, 240), "#315fc6").save(out, "PNG")
    return out.getvalue()


def generator(tmp_path, handler, **overrides):
    config = Settings(cloudflare_account_id="a" * 32, cloudflare_api_token="test-secret", upload_dir=str(tmp_path), **overrides)
    router = ModelRouter({"image": TaskConfig(provider="cloudflare", model="@cf/test/image")})
    return IllustrationGenerator(config, router, transport=httpx.MockTransport(handler))


async def test_provider_uses_router_and_persists_validated_image_without_credentials(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"success": True, "result": {"image": base64.b64encode(png()).decode()}, "errors": [], "messages": []})
    generate = generator(tmp_path, handler)
    asset = await generate("A teacher helping a small group, no text")
    assert asset["status"] == "ready" and asset["kind"] == "illustration"
    assert asset["provider"] == "cloudflare"
    assert asset["meta"]["model"] == "@cf/test/image"
    assert "test-secret" not in str(asset)
    assert read_illustration(tmp_path, asset["id"]).startswith(b"\x89PNG")
    assert (await generate("A teacher helping a small group, no text"))["id"] == asset["id"]
    assert len(calls) == 1
    assert calls[0].url.path == "/client/v4/accounts/" + "a" * 32 + "/ai/run/@cf/test/image"
    assert calls[0].headers["Authorization"] == "Bearer test-secret"
    assert b'"steps":4' in calls[0].content


@pytest.mark.parametrize("response", [
    httpx.Response(429, text="test-secret quota detail"),
    httpx.Response(200, json={"success": False, "errors": [{"message": "test-secret"}]}),
    httpx.Response(200, json={"success": True, "result": {"image": "bad!"}}),
    httpx.Response(200, json={"success": True, "result": {"image": base64.b64encode(b"not an image").decode()}}),
])
async def test_failures_are_safe_and_never_create_ready_assets(tmp_path, response):
    generate = generator(tmp_path, lambda _: response)
    with pytest.raises(IllustrationError) as caught:
        await generate("A classroom without lettering")
    assert "test-secret" not in str(caught.value)
    assert not list(tmp_path.rglob("*.png"))


async def test_generation_budget_limits_network_calls_and_timeout_is_safe(tmp_path):
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("test-secret", request=request)
    generate = generator(tmp_path, handler)
    for prompt in ("First scene", "Second scene", "Third scene"):
        with pytest.raises(IllustrationError) as caught:
            await generate(prompt)
        assert "test-secret" not in str(caught.value)
    assert count == 2


def test_asset_reader_rejects_path_traversal(tmp_path):
    with pytest.raises(IllustrationError):
        read_illustration(tmp_path, "../../private")


async def test_failed_tool_marks_retryable_asset_and_still_allows_section_submission():
    async def unavailable(_):
        raise IllustrationError("Illustration temporarily unavailable")
    deps = SectionDeps(search_materials=unavailable, make_diagram=unavailable, request_illustration=unavailable)
    tools = {t.name: t for t in build_section_tools(deps)}
    result = await tools["request_illustration"].fn({"prompt": "A classroom"})
    assert result["status"] == "failed" and result["retryable"]
    assert deps.assets[0]["status"] == "failed"
    await tools["write_section"].fn({"slides": [{"id": "s1"}]})
    assert deps.written_slides == [{"id": "s1"}]


def test_cloudflare_secret_is_redacted_in_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_CONFIG_FILE", str(tmp_path / "absent.yaml"))
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-secret")
    settings = Settings()
    assert settings.cloudflare_api_token.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)


async def test_image_failure_preserves_the_complete_draft_and_reports_retryable_assets():
    from app.demo_pipeline import FakeSectionModel, fake_search, fake_make_diagram
    from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course
    class ScenarioModel(FakeSectionModel):
        def _decide(self, messages, tools):
            response = super()._decide(messages, tools)
            for call in response.tool_calls or []:
                if call.name == "make_diagram":
                    call.name = "request_illustration"
                    call.arguments = {"prompt": "A classroom without text"}
                if call.name == "write_section":
                    for slide in call.arguments["slides"]:
                        for visual in slide["visuals"]:
                            visual["kind"] = "illustration"
            return response
    async def failed(_):
        raise IllustrationError("Image service unavailable")
    result = await generate_course(GenerationRequest(topic="Teamwork", audience="Beginners", duration_min=30), PipelineDeps(client=ScenarioModel(), model="test", search_materials=fake_search, make_diagram=fake_make_diagram, request_illustration=failed))
    assert len(result.package.slide_deck.slides) == 12
    assert all(a.status == "failed" and a.meta["retryable"] for a in result.package.assets)
    assert len(result.assembly_errors) == 3
    for agent in result.agents:
        names = agent.call_names
        assert names.index("request_illustration") < names.index("write_section")
        assert agent.stopped_by == "terminal"
