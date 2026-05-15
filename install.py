"""Install EFLOWCODE Image MCP into Codex and/or Claude Desktop."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_BASE_URL = "https://e-flowcode.cc/v1"
DEFAULT_MODEL = "gpt-5.5"


def _backup(path: Path) -> None:
    if path.exists():
        backup = path.with_name(f"{path.name}.bak.{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"Backed up {path} -> {backup}")


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _install_deps(repo_root: Path) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(repo_root)])


def _collect_env(args: argparse.Namespace) -> dict[str, str]:
    api_key = args.api_key or os.environ.get("EFLOWCODE_API_KEY", "")
    if not api_key and not args.no_prompt:
        api_key = getpass.getpass("EFLOWCODE API key: ").strip()
    if not api_key:
        raise SystemExit("Missing API key. Pass --api-key or set EFLOWCODE_API_KEY.")

    save_dir = args.save_dir or str(Path.home() / "Pictures" / "eflowcode-image-out")
    return {
        "EFLOWCODE_API_KEY": api_key,
        "EFLOWCODE_BASE_URL": args.base_url,
        "EFLOWCODE_MODEL": args.model,
        "EFLOWCODE_SAVE_DIR": save_dir,
        "EFLOWCODE_SAVE_DIR_ROOT": args.save_dir_root or save_dir,
    }


def _write_codex(server_path: Path, env: dict[str, str]) -> Path:
    cfg_dir = Path.home() / ".codex"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "config.toml"
    block = (
        "\n[mcp_servers.eflowcode-image]\n"
        f"command = {_json_string(sys.executable)}\n"
        f"args = [{_json_string(str(server_path))}]\n"
        "env = { "
        + ", ".join(f"{k} = {_json_string(v)}" for k, v in env.items())
        + " }\n"
    )
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8")
        if "[mcp_servers.eflowcode-image]" in text:
            print(f"Codex config already contains [mcp_servers.eflowcode-image], leaving it unchanged: {cfg}")
            return cfg
        _backup(cfg)
        with cfg.open("a", encoding="utf-8") as f:
            f.write(block)
    else:
        cfg.write_text(block.lstrip(), encoding="utf-8")
    print(f"Wrote Codex config: {cfg}")
    return cfg


def _write_claude(server_path: Path, env: dict[str, str]) -> Path:
    cfg = Path.home() / ".claude.json"
    data: dict = {}
    if cfg.exists():
        _backup(cfg)
        data = json.loads(cfg.read_text(encoding="utf-8"))
    servers = data.setdefault("mcpServers", {})
    servers["eflowcode-image"] = {
        "command": sys.executable,
        "args": [str(server_path)],
        "env": env,
    }
    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote Claude config: {cfg}")
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="Install EFLOWCODE Image MCP")
    parser.add_argument("--api-key", default=None, help="EFLOWCODE API key")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--save-dir", default=None)
    parser.add_argument("--save-dir-root", default=None)
    parser.add_argument("--no-codex", action="store_true")
    parser.add_argument("--no-claude", action="store_true")
    parser.add_argument("--no-deps", action="store_true")
    parser.add_argument("--no-prompt", action="store_true", help="Do not prompt for missing API key")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    server_path = repo_root / "server.py"
    if not args.no_deps:
        _install_deps(repo_root)
    env = _collect_env(args)
    if not args.no_codex:
        _write_codex(server_path, env)
    if not args.no_claude:
        _write_claude(server_path, env)
    print("Done. Restart your MCP client, then call server_info.")


if __name__ == "__main__":
    main()
