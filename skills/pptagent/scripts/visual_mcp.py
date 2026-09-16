#!/usr/bin/env python3
"""Workspace-bound stdio MCP adapter for the skill's external visual review."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pptagent_runtime.config import SKILL_ROOT, load_config, visual_settings


def create_server(
    workspace: Path,
    config_path: Path | None = None,
    env_path: Path | None = None,
) -> FastMCP:
    workspace = workspace.expanduser().resolve()
    if not (workspace / "task.json").is_file():
        raise ValueError("workspace must contain task.json; run the skill's init first")
    config_path = config_path.resolve() if config_path else None
    env_path = env_path.resolve() if env_path else None
    server = FastMCP("PPTAgent Visual Review")
    lock = asyncio.Lock()

    async def run_review(command: str, force: bool = False) -> dict[str, Any]:
        # One process per review isolates browser lifetimes and keeps stdout valid MCP.
        async with lock:
            config = load_config(config_path, env_path)
            if config["mode"] != "text":
                raise ToolError("visual MCP requires mode: text in the skill config")
            settings = visual_settings(config)
            if not all(settings[key] for key in ("base_url", "model", "api_key")):
                raise ToolError(
                    "Configure visual.base_url, visual.model and the API key"
                )
            argv = [sys.executable, str(SKILL_ROOT / "scripts/pptagent.py")]
            for flag, value in (("--config", config_path), ("--env", env_path)):
                if value:
                    argv.extend([flag, str(value)])
            argv.extend([command, "--workspace", str(workspace)])
            if force:
                argv.append("--force")
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _stderr = await asyncio.wait_for(
                    process.communicate(), timeout=1800
                )
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise ToolError(
                    "Review CLI returned invalid JSON; run it locally to diagnose"
                ) from exc
            if process.returncode and "error" in payload:
                message = str(payload["error"]).replace(
                    settings["api_key"], "[redacted]"
                )
                raise ToolError(message)
            return payload

    @server.tool()
    async def review_slides(force: bool = False) -> dict[str, Any]:
        """Render and review all slide HTML in the configured workspace using the visual model.

        Saves current render/review evidence. A fail or unjudgeable verdict is not
        a tool transport error: fix the reported issues and call this tool again.
        Unchanged passing reviews from the same reviewer are reused unless force is true.
        """
        return await run_review("review-slides", force)

    @server.tool()
    async def review_deck() -> dict[str, Any]:
        """Render answer.pptx with LibreOffice, review contact sheets, and save review evidence.

        Run the skill's build first. After a pass, run its finalize command to
        verify that the reviewed deck matches the current sources.
        """
        return await run_review("review-deck")

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="PPTAgent visual review MCP (stdio)")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--env", type=Path)
    args = parser.parse_args()
    create_server(args.workspace, args.config, args.env).run(show_banner=False)


if __name__ == "__main__":
    main()
