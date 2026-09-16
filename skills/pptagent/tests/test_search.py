"""Serper wire-format checks without making paid requests."""

from __future__ import annotations

import importlib.util
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponseError

ROOT = Path(__file__).resolve().parents[3]


class SerperTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                owner.requests.append(
                    {
                        "path": self.path,
                        "key": self.headers.get("X-API-KEY"),
                        "body": json.loads(
                            self.rfile.read(int(self.headers["Content-Length"]))
                        ),
                    }
                )
                payload = {
                    "organic": [
                        {
                            "title": "Source",
                            "link": "https://example.org/paper",
                            "snippet": "Evidence",
                        }
                    ],
                    "images": [
                        {
                            "imageUrl": "https://example.org/figure.png",
                            "title": "Figure",
                        }
                    ],
                }
                self.send_response(owner.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, format: str, *args: Any) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with patch.dict(
            os.environ,
            {
                "SERPER_API_KEY": "fixture-secret",
                "SERPAPI_KEY": "",
                "TAVILY_API_KEY": "",
            },
        ):
            spec = importlib.util.spec_from_file_location(
                "serper_under_test", ROOT / "deeppresenter/tools/search.py"
            )
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.module.SERPER_API_URL = f"http://127.0.0.1:{server.server_port}"

    async def test_web_and_image_results_share_existing_contract(self) -> None:
        result = await self.module.search_web.fn(
            "test query", max_results=2, time_range="month"
        )
        self.assertEqual(result["results"][0]["url"], "https://example.org/paper")
        self.assertEqual(result["total_results"], 1)
        self.assertEqual(
            self.requests[0],
            {
                "path": "/search",
                "key": "fixture-secret",
                "body": {"q": "test query", "num": 2, "tbs": "qdr:m"},
            },
        )
        images = await self.module.search_images.fn("figure")
        self.assertEqual(images["images"][0]["url"], "https://example.org/figure.png")
        self.assertEqual(self.requests[1]["path"], "/images")

    async def test_existing_serpapi_configuration_keeps_precedence(self) -> None:
        self.module.GOOGLE_KEYS = ["existing-key"]
        with patch.object(
            self.module,
            "_serpapi_request",
            new=AsyncMock(return_value={"organic_results": []}),
        ) as request:
            result = await self.module.search_web.fn("query")
        request.assert_awaited_once()
        self.assertEqual(result["total_results"], 0)
        self.assertEqual(self.requests, [])

    async def test_http_failure_does_not_expose_key(self) -> None:
        self.status = 401
        with self.assertRaises(ClientResponseError) as caught:
            await self.module.search_web.fn("query")
        self.assertNotIn("fixture-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
