"""Generate optional unlabelled illustrations; render/export only read saved PNGs.

One instance per generation job: at most two external attempts, duplicate prompts
reuse a result within that job. Opaque IDs and chapter authorization protect files.
No remote URLs, credentials or filesystem paths enter the course IR.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4

import httpx
from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.llm.router import ModelRouter

MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class IllustrationError(RuntimeError):
    """Safe user-facing failure. Never include upstream response bodies."""


def read_illustration(upload_dir: str | Path, asset_id: str) -> bytes:
    if not re.fullmatch(r"il-[a-f0-9]{32}", asset_id):
        raise IllustrationError("Invalid illustration identifier")
    try:
        return (Path(upload_dir) / "illustrations" / f"{asset_id}.png").read_bytes()
    except OSError:
        raise IllustrationError("Illustration is unavailable; regenerate to retry") from None


def _save_image(upload_dir: str | Path, data: bytes, asset_id: str) -> None:
    if len(data) > MAX_IMAGE_BYTES:
        raise IllustrationError("Illustration exceeds the image size limit")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or not (0 < image.width * image.height <= 16_000_000):
                raise IllustrationError("Unsupported illustration format or dimensions")
            output = io.BytesIO()
            image.convert("RGB").save(output, "PNG")
            clean = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise IllustrationError("Invalid illustration image") from None
    if len(clean) > MAX_IMAGE_BYTES:
        raise IllustrationError("Illustration exceeds the image size limit")
    directory = Path(upload_dir) / "illustrations"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(clean)
        os.replace(temporary, directory / f"{asset_id}.png")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class IllustrationGenerator:
    def __init__(self, settings: Settings, router: ModelRouter, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.router = router
        self.transport = transport
        self._lock = asyncio.Lock()
        self._attempts = 0
        self._cache: dict[str, dict] = {}

    async def __call__(self, prompt: str) -> dict:
        prompt = prompt.strip()
        suffix = ". Professional educational illustration, clear composition, no text, no letters, no labels, no logos, no watermarks."
        if not prompt or len(prompt + suffix) > 2048:
            raise IllustrationError("Illustration prompt must fit within 2048 characters")
        task = self.router.for_task("image")
        account = self.settings.cloudflare_account_id.strip()
        token = self.settings.cloudflare_api_token.get_secret_value().strip()
        if task.provider != "cloudflare" or not task.model or not re.fullmatch(r"@cf/[a-zA-Z0-9_./-]+", task.model):
            raise IllustrationError("Image provider is not configured")
        if not re.fullmatch(r"[a-fA-F0-9]{32}", account) or not token:
            raise IllustrationError("Cloudflare account ID or API token is not configured")
        async with self._lock:
            if prompt in self._cache:
                return self._cache[prompt]
            if self._attempts >= 2:
                raise IllustrationError("This generation's two-image budget is exhausted; keep the text and retry in a new generation")
            self._attempts += 1
            url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{task.model}"
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=60, follow_redirects=False) as client:
                    async with client.stream("POST", url, headers={"Authorization": f"Bearer {token}"}, json={"prompt": prompt + suffix, "steps": 4}) as response:
                        if response.status_code != 200:
                            raise IllustrationError(f"Image service unavailable (HTTP {response.status_code}); keep the text and retry later")
                        raw = bytearray()
                        async for part in response.aiter_bytes():
                            raw.extend(part)
                            if len(raw) > MAX_RESPONSE_BYTES:
                                raise IllustrationError("Image service response exceeds the size limit")
                payload = json.loads(raw)
                if payload.get("success") is False:
                    raise IllustrationError("Image service could not generate this illustration; retry later")
                data = base64.b64decode(payload["result"]["image"], validate=True)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, binascii.Error):
                raise IllustrationError("Image service returned no valid image; retry later") from None
            asset_id = f"il-{uuid4().hex}"
            try:
                await asyncio.to_thread(_save_image, self.settings.upload_dir, data, asset_id)
            except OSError:
                raise IllustrationError("Illustration could not be saved; retry later") from None
            asset = {
                "id": asset_id, "kind": "illustration", "status": "ready",
                "provider": task.provider, "spec": {"prompt": prompt, "resolvedPrompt": prompt + suffix},
                "meta": {"model": task.model, "steps": 4, "generated": True},
                "altText": prompt,
            }
            self._cache[prompt] = asset
            return asset
