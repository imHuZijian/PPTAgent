"""Actual stdio MCP and HTTP contract tests; responses are fixtures, not model scores."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from pptagent_runtime import core
from pptagent_runtime.visual import review_images


class VisualMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="pptagent-mcp-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.workspace = self.directory / "deck"
        shutil.copytree(ROOT / "tests/fixtures/visual-review", self.workspace)
        self.requests: list[dict[str, Any]] = []
        self.reply = {
            "verdict": "pass",
            "summary": "Mock response for protocol testing",
            "issues": [],
        }
        self.finish_reason = "stop"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append({"path": self.path, "body": body})
                payload = {
                    "choices": [
                        {
                            "finish_reason": owner.finish_reason,
                            "message": {"content": json.dumps(owner.reply)},
                        }
                    ]
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, format: str, *args: Any) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.config = {
            "mode": "text",
            "visual": {
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "fixture-model",
                "api_key_env": "PPTAGENT_TEST_VISUAL_KEY",
            },
            "delivery": {"mode": "strict"},
        }
        self.config_path = self.directory / "config.json"
        self.config_path.write_text(json.dumps(self.config))
        self.key = patch.dict(os.environ, {"PPTAGENT_TEST_VISUAL_KEY": "fixture-key"})
        self.key.start()
        self.addCleanup(self.key.stop)

    async def test_stdio_review_build_and_rejection(self) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                str(ROOT / "scripts/visual_mcp.py"),
                "--workspace",
                str(self.workspace),
                "--config",
                str(self.config_path),
            ],
            env=os.environ.copy(),
        )
        async with stdio_client(params) as (reader, writer):  # noqa: SIM117
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                listed = await session.list_tools()
                self.assertEqual(
                    {tool.name for tool in listed.tools},
                    {"review_slides", "review_deck"},
                )
                result = await session.call_tool("review_slides", {})
                self.assertFalse(result.isError)
                self.assertFalse(
                    core.review_gaps(self.workspace, core.slide_files(self.workspace))
                )
                self.assertEqual(len(self.requests), 3)
                request = self.requests[0]
                self.assertEqual(request["path"], "/v1/chat/completions")
                content = request["body"]["messages"][1]["content"]
                self.assertTrue(
                    content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
                )
                await core.build(self.workspace, self.config)
                self.assertEqual(
                    core.pptx_info(self.workspace / "answer.pptx"), (3, "16:9")
                )
                if core.office_command():
                    result = await session.call_tool("review_deck", {})
                    self.assertFalse(result.isError)
                    self.assertTrue(
                        core.finalize(self.workspace, self.config)["complete"]
                    )
                self.reply = {
                    "verdict": "fail",
                    "summary": "Mock clipping",
                    "issues": [
                        {
                            "severity": "major",
                            "slide": 1,
                            "description": "Clipped text",
                            "suggested_fix": "Resize",
                        }
                    ],
                }
                result = await session.call_tool("review_slides", {})
                self.assertFalse(result.isError)
                self.assertFalse(
                    core.review_gaps(self.workspace, core.slide_files(self.workspace))
                )
                result = await session.call_tool("review_slides", {"force": True})
                self.assertFalse(result.isError)
                self.assertTrue(
                    core.review_gaps(self.workspace, core.slide_files(self.workspace))
                )
                self.assertFalse(core.finalize(self.workspace, self.config)["complete"])
                self.reply = {"verdict": "pass", "summary": "Malformed review"}
                result = await session.call_tool("review_slides", {})
                self.assertTrue(result.isError)
                requests_before = len(self.requests)
                self.config["visual"]["api_key_env"] = "PPTAGENT_MISSING_TEST_KEY"
                self.config_path.write_text(json.dumps(self.config))
                result = await session.call_tool("review_slides", {})
                self.assertTrue(result.isError)
                self.assertEqual(len(self.requests), requests_before)

    async def test_truncated_review_does_not_record_acceptance(self) -> None:
        rendered = await core.render_slides(self.workspace)
        image = self.workspace / rendered["renders"][0]
        before = core.load_state(self.workspace)
        self.finish_reason = "length"
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            await asyncio.to_thread(review_images, self.config, [image], "Review")
        self.assertEqual(core.load_state(self.workspace), before)


if __name__ == "__main__":
    unittest.main()
