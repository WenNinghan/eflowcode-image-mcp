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

---

# EFLOWCODE Image MCP 中文说明

这是一个面向 EFLOWCODE 的图像生成 MCP 服务。它通过 Responses API 调用支持 `image_generation` 工具的 `gpt-5.5` 模型，让 Codex、Claude Desktop、Claude Code、Cursor 等 MCP 客户端可以直接生图、改图和多图参考生成。

服务默认调用：

```text
POST {EFLOWCODE_BASE_URL}/responses
model: gpt-5.5
tools: [{"type": "image_generation"}]
```

默认会在发送给模型前给提示词加上 `不改写：` 前缀。

## 功能

- `image_generate`：文本生成图像
- `image_edit`：基于单张本地图片进行编辑或参考生成
- `image_batch_edit`：对多张图片逐张执行同一编辑指令
- `image_multi_reference`：使用 2-10 张参考图合成一张新图
- 图片自动保存到本地目录
- 输出目录沙箱保护，避免写到非预期路径
- 输入图片格式和大小校验，支持 PNG、JPEG、WebP、GIF
- 可用于 EFLOWCODE 或任何兼容 `/v1/responses` 且支持 `image_generation` 的接口

## 安装

```bash
git clone https://github.com/WenNinghan/eflowcode-image-mcp.git
cd eflowcode-image-mcp
python -m pip install -e .
```

安装后需要把 MCP 服务配置到你的客户端中。

## Codex 快速配置

```bash
python install.py --api-key sk-your-key --no-claude
```

执行后重启 Codex，然后让 Codex 调用 `server_info` 验证配置。

安装脚本会把 MCP 配置追加到 `~/.codex/config.toml`，并在写入前备份原配置。

## Codex 手动配置

把下面内容加入 `~/.codex/config.toml`：

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

Windows 路径需要转义反斜杠：

```toml
args = ["C:\\Users\\you\\eflowcode-image-mcp\\server.py"]
```

## Claude Desktop / Claude Code 配置

在 MCP 配置中加入：

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

## 环境变量

| 变量 | 是否必填 | 默认值 | 说明 |
|---|---:|---|---|
| `EFLOWCODE_API_KEY` | 是 | - | 用作 Bearer token 的 API key |
| `EFLOWCODE_BASE_URL` | 否 | `https://e-flowcode.cc/v1` | 接口 Base URL，不包含 `/responses` |
| `EFLOWCODE_MODEL` | 否 | `gpt-5.5` | 用于 Responses 图像生成的模型 |
| `EFLOWCODE_PROMPT_PREFIX` | 否 | `不改写：` | 自动添加到所有提示词前的前缀 |
| `EFLOWCODE_SAVE_DIR` | 否 | `~/Pictures/eflowcode-image-out` | 默认图片输出目录 |
| `EFLOWCODE_SAVE_DIR_ROOT` | 否 | 同输出目录 | 输出目录沙箱根路径 |
| `EFLOWCODE_USE_SHELL_PROXY` | 否 | `0` | 设为 `1` 时允许 httpx 使用系统代理环境变量 |

也兼容 `EF_API_KEY`、`EF_BASE_URL`、`EF_MODEL` 和 `OPENAI_API_KEY`。

## 工具说明

### `server_info`

返回当前服务模式、Base URL、模型、保存目录和限制信息。

### `image_generate`

根据文本生成图片。

常用参数：

- `prompt`：图片提示词
- `size`：可选，格式为 `宽x高`，默认 `1024x1024`
- `n`：生成数量，范围 1-10
- `model`：可选模型覆盖
- `save_dir`：可选输出目录，必须位于 `EFLOWCODE_SAVE_DIR_ROOT` 下
- `basename`：可选文件名前缀

### `image_edit`

使用一张本地图片作为输入参考，结合提示词生成新图。

常用参数包括 `prompt`、`image_path`、`size`、`model`、`save_dir` 和 `basename`。

`mask_path` 参数会被保留用于接口兼容，但当前 Responses 实现不会单独上传 alpha mask。如果需要指定编辑区域，请直接在提示词中描述。

### `image_batch_edit`

对多张图片逐张执行同一编辑提示词。每张图片会发起一次独立请求。

### `image_multi_reference`

使用 2-10 张本地参考图生成一张新图。

## 使用示例

文本生图：

```text
生成一张 16:9 的科研汇报封面图，主题是智能优化算法和城市交通。
```

单图编辑：

```text
把 C:\Pictures\apple.png 里的苹果改成蓝色，保持白色背景。
```

多图参考：

```text
参考这两张产品图，生成一张同风格的干净产品海报。
```

## 响应解析

服务会从 `response.output` 中提取如下结构里的 base64 图片：

```json
{
  "type": "image_generation_call",
  "result": "..."
}
```

如果没有找到图片结果，工具会返回明确错误，并附带简短的响应摘要，方便排查接口兼容性。

## 安全说明

- API key 只会发送到 `EFLOWCODE_BASE_URL`
- 工具运行时不接受动态 Base URL 参数，避免提示词注入导致 key 外泄
- 输出路径会被限制在 `EFLOWCODE_SAVE_DIR_ROOT` 下
- 上传前会校验输入图片的 magic bytes 和文件大小
- 写入本地前会限制生成图片的响应大小

## 许可证

MIT
