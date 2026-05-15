"""EFLOWCODE Image MCP server using Responses image_generation."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_BASEURL = (
    os.environ.get("EFLOWCODE_BASE_URL")
    or os.environ.get("EF_BASE_URL")
    or "https://e-flowcode.cc/v1"
).rstrip("/")
API_KEY = (
    os.environ.get("EFLOWCODE_API_KEY", "")
    or os.environ.get("EF_API_KEY", "")
    or os.environ.get("OPENAI_API_KEY", "")
)
DEFAULT_MODEL = (
    os.environ.get("EFLOWCODE_MODEL")
    or os.environ.get("EF_MODEL")
    or "gpt-5.5"
)
PROMPT_PREFIX = (
    os.environ.get("EFLOWCODE_PROMPT_PREFIX")
    or os.environ.get("EF_PROMPT_PREFIX")
    or "不改写："
)
_TRUST_ENV = (
    os.environ.get("EFLOWCODE_USE_SHELL_PROXY")
    or os.environ.get("EF_USE_SHELL_PROXY")
    or ""
).strip().lower() in {"1", "true", "yes"}

_SAVE_ROOT = Path(
    os.environ.get("EFLOWCODE_SAVE_DIR_ROOT")
    or os.environ.get("EF_SAVE_DIR_ROOT")
    or str(Path.home() / "Pictures" / "eflowcode-image-out")
).expanduser().resolve()
DEFAULT_SAVE_DIR = Path(
    os.environ.get("EFLOWCODE_SAVE_DIR")
    or os.environ.get("EF_SAVE_DIR")
    or str(_SAVE_ROOT)
).expanduser()

MAX_N = 10
MIN_SIZE_EDGE = 256
MAX_SIZE_EDGE = 4096
SIZE_ALIGNMENT = 8
MAX_INPUT_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
_SAFE_BASENAME_RE = re.compile(r"^[A-Za-z0-9_\-.]+$")

mcp = FastMCP("eflowcode-image")


@dataclass
class ImageInput:
    path: Path
    raw: bytes
    mime: str


def _get_key(override: str | None) -> str:
    key = (override or "").strip() or API_KEY
    if not key:
        raise RuntimeError(
            "No API key configured. Set EFLOWCODE_API_KEY, EF_API_KEY, or OPENAI_API_KEY."
        )
    return key


def _validate_n(n: int) -> str | None:
    if not isinstance(n, int) or isinstance(n, bool):
        return f"n 必须是整数，收到 {type(n).__name__}"
    if n < 1:
        return f"n 必须 >= 1，收到 {n}"
    if n > MAX_N:
        return f"n 必须 <= {MAX_N}，收到 {n}"
    return None


def _validate_size(size: str | None, *, allow_none: bool = True) -> tuple[str | None, str | None]:
    if size is None:
        if allow_none:
            return None, None
        return None, "size 不能为空"
    if not isinstance(size, str):
        return None, f"size 必须是字符串，收到 {type(size).__name__}"
    s = size.strip().lower()
    m = re.match(r"^(\d+)x(\d+)$", s)
    if not m:
        return None, f"size 格式错误：必须是 'WxH'，收到 {size!r}"
    w, h = int(m.group(1)), int(m.group(2))
    if w < MIN_SIZE_EDGE or h < MIN_SIZE_EDGE:
        return None, f"size 边长太小（最小 {MIN_SIZE_EDGE}），收到 {size}"
    if w > MAX_SIZE_EDGE or h > MAX_SIZE_EDGE:
        return None, f"size 边长太大（最大 {MAX_SIZE_EDGE}），收到 {size}"
    if w % SIZE_ALIGNMENT != 0 or h % SIZE_ALIGNMENT != 0:
        return None, f"size W/H 必须是 {SIZE_ALIGNMENT} 的倍数，收到 {size}"
    return f"{w}x{h}", None


def _safe_basename(name: str | None) -> str | None:
    if name is None:
        return None
    if not isinstance(name, str) or not name.strip():
        return None
    only = Path(name).name
    if only != name or ".." in only or only.startswith("."):
        return None
    if not _SAFE_BASENAME_RE.match(only) or len(only) > 100:
        return None
    return only


def _default_basename(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}"


def _resolve_save_dir(save_dir: str | None) -> tuple[Path | None, str | None]:
    try:
        _SAVE_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return None, f"无法创建 save root {_SAVE_ROOT}: {e}"

    if save_dir is None:
        p = DEFAULT_SAVE_DIR
    else:
        p = Path(save_dir).expanduser()
    try:
        resolved = p.resolve()
        resolved.relative_to(_SAVE_ROOT)
    except (ValueError, OSError):
        return None, (
            f"save_dir 必须在安全根目录 {_SAVE_ROOT} 之下；收到 {save_dir!r}。"
            "留空使用默认目录。"
        )
    return resolved, None


def _mime_from_magic(raw: bytes) -> str | None:
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:4] == b"RIFF" and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _validate_image_path(image_path: str, label: str = "image_path") -> tuple[ImageInput | None, str | None]:
    p = Path(image_path).expanduser()
    if not p.is_file():
        return None, f"{label} 不存在: {p}"
    try:
        size = p.stat().st_size
    except OSError as e:
        return None, f"{label} 无法读取文件信息: {e}"
    if size > MAX_INPUT_FILE_BYTES:
        return None, f"{label} 超过单图上限 {MAX_INPUT_FILE_BYTES // 1024 // 1024}MB"
    try:
        raw = p.read_bytes()
    except OSError as e:
        return None, f"{label} 无法读取: {e}"
    mime = _mime_from_magic(raw)
    if not mime:
        return None, f"{label} 不是 PNG/JPEG/WebP/GIF"
    return ImageInput(path=p, raw=raw, mime=mime), None


def _data_url(image: ImageInput) -> str:
    encoded = base64.b64encode(image.raw).decode("ascii")
    return f"data:{image.mime};base64,{encoded}"


def _input_image_item(image: ImageInput) -> dict[str, Any]:
    return {"type": "input_image", "image_url": _data_url(image)}


def _prefixed_prompt(prompt: str) -> str:
    stripped = prompt.strip()
    if stripped.startswith(PROMPT_PREFIX):
        return stripped
    return f"{PROMPT_PREFIX}{stripped}"


def _prompt_with_size(prompt: str, size: str | None) -> str:
    prefixed = _prefixed_prompt(prompt)
    if not size:
        return prefixed
    return f"{prefixed}\n\n尺寸要求：{size}。"


def _extract_image_results(resp: dict[str, Any]) -> list[str]:
    results: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "image_generation_call" and isinstance(value.get("result"), str):
                results.append(value["result"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(resp.get("output", []))
    return results


def _response_summary(resp: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": resp.get("id"),
        "status": resp.get("status"),
        "model": resp.get("model"),
        "output_types": [
            item.get("type")
            for item in resp.get("output", [])
            if isinstance(item, dict)
        ],
        "error": resp.get("error"),
    }


def _detect_png_size(raw: bytes) -> tuple[int, int] | None:
    if len(raw) >= 24 and raw[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    return None


def _save_image_b64(b64: str, out_dir: Path, stem: str, index: int | None = None) -> dict[str, Any]:
    clean = re.sub(r"\s+", "", b64)
    if "," in clean and clean.startswith("data:image/"):
        clean = clean.split(",", 1)[1]
    raw = base64.b64decode(clean)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"响应图片超过 {MAX_RESPONSE_BYTES // 1024 // 1024}MB 上限")
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if index is None else f"_{index}"
    path = out_dir / f"{stem}{suffix}.png"
    path.write_bytes(raw)
    actual_size = _detect_png_size(raw)
    return {
        "path": str(path),
        "size_bytes": len(raw),
        "actual_size": list(actual_size) if actual_size else None,
        "actual_megapixels": round((actual_size[0] * actual_size[1]) / 1_000_000, 3) if actual_size else None,
    }


async def _responses_image_request(
    *,
    key: str,
    prompt: str,
    size: str | None,
    images: list[ImageInput] | None = None,
    model: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    effective_model = model or DEFAULT_MODEL
    text = _prompt_with_size(prompt, size)

    if images:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
        content.extend(_input_image_item(image) for image in images)
        input_payload: Any = [{"role": "user", "content": content}]
    else:
        input_payload = text

    body = {
        "model": effective_model,
        "input": input_payload,
        "tools": [{"type": "image_generation"}],
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=600.0, trust_env=_TRUST_ENV) as client:
        response = await client.post(f"{DEFAULT_BASEURL}/responses", headers=headers, json=body)

    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {"raw_text": response.text[:2000]}
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"HTTP {response.status_code}: {json.dumps(payload, ensure_ascii=False)[:2000]}")

    results = _extract_image_results(payload if isinstance(payload, dict) else {})
    return results, payload if isinstance(payload, dict) else {"raw": payload}


def _validate_common(
    prompt: str,
    size: str | None,
    save_dir: str | None,
    basename: str | None,
    *,
    allow_size_none: bool = True,
) -> tuple[str | None, Path | None, str | None, str | None]:
    if not isinstance(prompt, str) or not prompt.strip():
        return None, None, None, "prompt 不能为空"
    cleaned_size, size_err = _validate_size(size, allow_none=allow_size_none)
    if size_err:
        return None, None, None, size_err
    safe_stem = _safe_basename(basename) if basename is not None else None
    if basename is not None and safe_stem is None:
        return None, None, None, "basename 含非法字符或路径分量；仅允许 [A-Za-z0-9_-.]"
    out_dir, dir_err = _resolve_save_dir(save_dir)
    if dir_err:
        return None, None, None, dir_err
    return cleaned_size, out_dir, safe_stem, None


@mcp.tool()
async def image_generate(
    prompt: str,
    size: str | None = "1024x1024",
    n: int = 1,
    model: str | None = None,
    save_dir: str | None = None,
    basename: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """文本生成图像。使用 gpt-5.5 /v1/responses + image_generation。"""
    err_n = _validate_n(n)
    if err_n:
        return {"ok": False, "error": err_n, "errors": [err_n]}
    cleaned_size, out_dir, safe_stem, err = _validate_common(prompt, size, save_dir, basename)
    if err:
        return {"ok": False, "error": err, "errors": [err]}
    key = _get_key(api_key)
    stem = safe_stem or _default_basename("gen")

    saved: list[dict[str, Any]] = []
    errors: list[str] = []
    summaries: list[dict[str, Any]] = []
    for i in range(n):
        try:
            results, resp = await _responses_image_request(
                key=key, prompt=prompt, size=cleaned_size, images=None, model=model
            )
            summaries.append(_response_summary(resp))
            if not results:
                errors.append(f"第 {i + 1} 张没有返回 image_generation_call.result: {_response_summary(resp)}")
                continue
            saved.append(_save_image_b64(results[0], out_dir, stem, i + 1 if n > 1 else None))  # type: ignore[arg-type]
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    return {
        "ok": bool(saved),
        "mode": "responses_image_generation",
        "base_url": DEFAULT_BASEURL,
        "model": model or DEFAULT_MODEL,
        "size": cleaned_size,
        "requested_n": n,
        "saved": saved,
        "errors": errors,
        "notes": [
            f"实际发送 prompt 以 {PROMPT_PREFIX!r} 开头",
            "使用 /v1/responses + image_generation tool",
        ],
        "response_summaries": summaries,
    }


@mcp.tool()
async def image_edit(
    prompt: str,
    image_path: str,
    mask_path: str | None = None,
    size: str = "1024x1024",
    model: str | None = None,
    save_dir: str | None = None,
    basename: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """单图参考/编辑。把本地图片作为 Responses image input 传入 image_generation。"""
    cleaned_size, out_dir, safe_stem, err = _validate_common(prompt, size, save_dir, basename, allow_size_none=False)
    if err:
        return {"ok": False, "error": err, "errors": [err]}
    image, image_err = _validate_image_path(image_path)
    if image_err:
        return {"ok": False, "error": image_err, "errors": [image_err]}
    notes = ["使用 Responses 多模态 input + image_generation"]
    if mask_path:
        notes.append("当前 Responses 模式不单独上传 alpha mask；mask_path 已忽略，需在 prompt 中描述编辑区域。")

    try:
        results, resp = await _responses_image_request(
            key=_get_key(api_key),
            prompt=f"基于输入图片进行编辑：{prompt}",
            size=cleaned_size,
            images=[image],  # type: ignore[list-item]
            model=model,
        )
        if not results:
            summary = _response_summary(resp)
            return {"ok": False, "error": "没有返回 image_generation_call.result", "response_summary": summary}
        saved = _save_image_b64(results[0], out_dir, safe_stem or _default_basename("edit"))  # type: ignore[arg-type]
        return {
            "ok": True,
            "mode": "responses_image_generation",
            "model": model or DEFAULT_MODEL,
            "size": cleaned_size,
            "saved": saved,
            "notes": notes,
            "response_summary": _response_summary(resp),
        }
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if any(token in msg.lower() for token in ("unsupported", "invalid", "input_image", "image_url")):
            msg = f"该接口暂不支持图像 input 或当前图片格式；原始错误: {msg}"
        return {"ok": False, "error": msg, "errors": [msg], "notes": notes}


@mcp.tool()
async def image_batch_edit(
    prompt: str,
    image_paths: list[str],
    size: str = "1024x1024",
    model: str | None = None,
    save_dir: str | None = None,
    basename: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """批量单图编辑。对每张图片独立调用 image_edit。"""
    if not isinstance(image_paths, list) or not image_paths:
        return {"ok": False, "error": "image_paths 必须是非空列表", "errors": ["image_paths 必须是非空列表"]}
    if len(image_paths) > MAX_N:
        return {"ok": False, "error": f"image_paths 最多 {MAX_N} 张", "errors": [f"image_paths 最多 {MAX_N} 张"]}

    results: list[dict[str, Any]] = []
    for idx, path in enumerate(image_paths, start=1):
        stem = f"{basename}_{idx}" if basename else None
        results.append(await image_edit(prompt, path, None, size, model, save_dir, stem, api_key))
    return {
        "ok": any(item.get("ok") for item in results),
        "mode": "responses_image_generation",
        "results": results,
        "notes": ["批量编辑按图片逐张串行执行，避免一次性请求过大。"],
    }


@mcp.tool()
async def image_multi_reference(
    prompt: str,
    image_paths: list[str],
    size: str = "1024x1024",
    model: str | None = None,
    save_dir: str | None = None,
    basename: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """多图参考生成一张新图。把多张本地图片作为 Responses image input。"""
    cleaned_size, out_dir, safe_stem, err = _validate_common(prompt, size, save_dir, basename, allow_size_none=False)
    if err:
        return {"ok": False, "error": err, "errors": [err]}
    if not isinstance(image_paths, list) or not 2 <= len(image_paths) <= MAX_N:
        msg = f"image_paths 必须包含 2-{MAX_N} 张图片"
        return {"ok": False, "error": msg, "errors": [msg]}

    images: list[ImageInput] = []
    total = 0
    for idx, path in enumerate(image_paths, start=1):
        image, image_err = _validate_image_path(path, f"image_paths[{idx}]")
        if image_err:
            return {"ok": False, "error": image_err, "errors": [image_err]}
        total += len(image.raw)  # type: ignore[union-attr]
        if total > MAX_TOTAL_INPUT_BYTES:
            msg = f"参考图累计超过 {MAX_TOTAL_INPUT_BYTES // 1024 // 1024}MB"
            return {"ok": False, "error": msg, "errors": [msg]}
        images.append(image)  # type: ignore[arg-type]

    try:
        results, resp = await _responses_image_request(
            key=_get_key(api_key),
            prompt=f"综合这些参考图片生成一张新图：{prompt}",
            size=cleaned_size,
            images=images,
            model=model,
        )
        if not results:
            summary = _response_summary(resp)
            return {"ok": False, "error": "没有返回 image_generation_call.result", "response_summary": summary}
        saved = _save_image_b64(results[0], out_dir, safe_stem or _default_basename("multiref"))  # type: ignore[arg-type]
        return {
            "ok": True,
            "mode": "responses_image_generation",
            "model": model or DEFAULT_MODEL,
            "n_references": len(images),
            "size": cleaned_size,
            "saved": saved,
            "notes": ["使用 Responses 多图片 input + image_generation"],
            "response_summary": _response_summary(resp),
        }
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if any(token in msg.lower() for token in ("unsupported", "invalid", "input_image", "image_url")):
            msg = f"该接口暂不支持多图 input；原始错误: {msg}"
        return {"ok": False, "error": msg, "errors": [msg]}


@mcp.tool()
def server_info() -> dict[str, Any]:
    """返回 Codex 生图 MCP 的当前配置和能力。"""
    auth_path = Path.home() / ".codex" / "auth.json"
    return {
        "name": "eflowcode-image",
        "mode": "responses_image_generation",
        "base_url": DEFAULT_BASEURL,
        "model": DEFAULT_MODEL,
        "prompt_prefix": PROMPT_PREFIX,
        "default_save_dir": str(DEFAULT_SAVE_DIR),
        "save_dir_root": str(_SAVE_ROOT),
        "api_key_configured": bool(API_KEY),
        "launcher_auth_json_available": auth_path.is_file(),
        "tools": {
            "image_generate": "文生图，调用 /v1/responses + image_generation",
            "image_edit": "单图参考/编辑，图片作为 Responses input_image",
            "image_batch_edit": "逐张调用 image_edit",
            "image_multi_reference": "多图参考合成，图片作为多个 Responses input_image",
        },
        "limits": {
            "n_range": f"1-{MAX_N}",
            "size_format": "WxH",
            "edge_range": f"{MIN_SIZE_EDGE}-{MAX_SIZE_EDGE}",
            "size_alignment": SIZE_ALIGNMENT,
            "single_input_image_mb": MAX_INPUT_FILE_BYTES // 1024 // 1024,
            "total_reference_mb": MAX_TOTAL_INPUT_BYTES // 1024 // 1024,
            "response_image_mb": MAX_RESPONSE_BYTES // 1024 // 1024,
        },
    }


async def _main() -> None:
    await mcp.run_stdio_async()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
