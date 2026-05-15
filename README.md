# EFLOWCODE Image MCP

MCP server for EFLOWCODE image generation through the Responses API.

It exposes image tools to MCP clients such as Codex, Claude Desktop, Claude Code, Cursor, and other MCP-compatible agents. The server calls:

```text
POST {EFLOWCODE_BASE_URL}/responses
model: gpt-5.5
tools: [{"type": "image_generation"}]
```

By default, prompts are prefixed with `不改写：` before being sent to the model.

## Features

- Text-to-image generation with `image_generate`
- Single image editing / reference generation with `image_edit`
- Batch image editing with `image_batch_edit`
- Multi-reference image synthesis with `image_multi_reference`
- Local file output with a save-directory sandbox
- Input image validation for PNG, JPEG, WebP, and GIF
- Works with EFLOWCODE or any compatible `/v1/responses` endpoint that supports `image_generation`

## Install

```bash
git clone https://github.com/WenNinghan/eflowcode-image-mcp.git
cd eflowcode-image-mcp
python -m pip install -e .
```

Then configure your MCP client.

## Quick Setup For Codex

```bash
python install.py --api-key sk-your-key --no-claude
```

Restart Codex, then ask your agent to call `server_info`.

The installer appends this MCP server to `~/.codex/config.toml` and backs up the existing config first.

## Manual Codex Config

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.eflowcode-image]
command = "python"
args = ["/absolute/path/to/eflowcode-image-mcp/server.py"]
env = {
  EFLOWCODE_API_KEY = "sk-your-key",
  EFLOWCODE_BASE_URL = "https://e-flowcode.cc/v1",
  EFLOWCODE_MODEL = "gpt-5.5",
  EFLOWCODE_SAVE_DIR = "~/Pictures/eflowcode-image-out",
  EFLOWCODE_SAVE_DIR_ROOT = "~/Pictures/eflowcode-image-out"
}
```

On Windows, use escaped paths:

```toml
args = ["C:\\Users\\you\\eflowcode-image-mcp\\server.py"]
```

## Claude Desktop / Claude Code

Add this to your MCP config:

```json
{
  "mcpServers": {
    "eflowcode-image": {
      "command": "python",
      "args": ["/absolute/path/to/eflowcode-image-mcp/server.py"],
      "env": {
        "EFLOWCODE_API_KEY": "sk-your-key",
        "EFLOWCODE_BASE_URL": "https://e-flowcode.cc/v1",
        "EFLOWCODE_MODEL": "gpt-5.5",
        "EFLOWCODE_SAVE_DIR": "~/Pictures/eflowcode-image-out",
        "EFLOWCODE_SAVE_DIR_ROOT": "~/Pictures/eflowcode-image-out"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---:|---|---|
| `EFLOWCODE_API_KEY` | yes | - | API key used as Bearer token |
| `EFLOWCODE_BASE_URL` | no | `https://e-flowcode.cc/v1` | Base URL without trailing endpoint path |
| `EFLOWCODE_MODEL` | no | `gpt-5.5` | Responses model used for image generation |
| `EFLOWCODE_PROMPT_PREFIX` | no | `不改写：` | Prefix added to all prompts |
| `EFLOWCODE_SAVE_DIR` | no | `~/Pictures/eflowcode-image-out` | Default output directory |
| `EFLOWCODE_SAVE_DIR_ROOT` | no | same as save dir | Sandbox root for output paths |
| `EFLOWCODE_USE_SHELL_PROXY` | no | `0` | Set to `1` to let httpx use shell proxy env vars |

Compatibility aliases are also accepted: `EF_API_KEY`, `EF_BASE_URL`, `EF_MODEL`, and `OPENAI_API_KEY`.

## Tools

### `server_info`

Returns current mode, base URL, model, save directory, and limits.

### `image_generate`

Generate images from text.

Arguments:

- `prompt`: image prompt
- `size`: optional `WxH`, default `1024x1024`
- `n`: number of images, 1-10
- `model`: optional override
- `save_dir`: optional output directory under `EFLOWCODE_SAVE_DIR_ROOT`
- `basename`: optional output filename stem

### `image_edit`

Generate a new image using one local image as an input reference.

Arguments include `prompt`, `image_path`, optional `size`, `model`, `save_dir`, and `basename`.

`mask_path` is accepted for interface compatibility, but this Responses implementation does not upload alpha masks separately. Describe the edit area in the prompt.

### `image_batch_edit`

Apply the same edit prompt to multiple images, one request per image.

### `image_multi_reference`

Generate one new image from 2-10 local reference images.

## Examples

Text-to-image:

```text
Generate a 16:9 research presentation cover about intelligent optimization algorithms and urban traffic.
```

Image edit:

```text
Edit C:\Pictures\apple.png so the apple becomes blue, keep the white background.
```

Multi-reference:

```text
Use these two product images as references and generate one clean poster in the same style.
```

## Response Handling

The server extracts base64 image data from `response.output` items where:

```json
{
  "type": "image_generation_call",
  "result": "..."
}
```

If no image result is found, the tool returns a clear error plus a compact response summary.

## Security Notes

- API keys are only sent to `EFLOWCODE_BASE_URL`.
- Runtime tools do not accept a base URL parameter, to avoid prompt-injection key exfiltration.
- Output paths are restricted to `EFLOWCODE_SAVE_DIR_ROOT`.
- Input images are checked by magic bytes and size limits before upload.
- Generated binary responses are capped before writing to disk.

## License

MIT
