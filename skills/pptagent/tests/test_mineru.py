"""MinerU public URL requests preserve hosted parsing and bypass local upload."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from deeppresenter.utils import mineru_api


class MinerUURLTests(unittest.IsolatedAsyncioTestCase):
    async def test_url_submission_uses_batch_api(self) -> None:
        response = AsyncMock()
        response.__aenter__.return_value = response
        response.raise_for_status = Mock()
        response.json.return_value = {"code": 0, "data": {"batch_id": "batch"}}
        session = Mock()
        session.post.return_value = response
        batch = await mineru_api._request_parse_url(
            session, "https://example.org/paper.pdf", "paper", "vlm", "fixture-key"
        )
        self.assertEqual(batch, "batch")
        session.post.assert_called_once_with(
            "https://mineru.net/api/v4/extract/task/batch",
            headers={"Authorization": "Bearer fixture-key"},
            json={
                "files": [{"url": "https://example.org/paper.pdf", "data_id": "paper"}],
                "model_version": "vlm",
            },
        )

    async def test_public_url_mode_never_uploads_local_bytes(self) -> None:
        with (
            tempfile.TemporaryDirectory() as output,
            patch.object(
                mineru_api, "_request_parse_url", new=AsyncMock(return_value="batch")
            ) as submit,
            patch.object(mineru_api, "_request_upload_url", new=AsyncMock()) as upload,
            patch.object(
                mineru_api,
                "_poll_result",
                new=AsyncMock(return_value="https://example.org/result.zip"),
            ) as poll,
            patch.object(
                mineru_api, "_download_and_extract", new=AsyncMock()
            ) as download,
        ):
            await mineru_api.parse_pdf_online(
                "paper.pdf",
                output,
                "fixture-key",
                source_url="https://example.org/paper.pdf",
            )
            submit.assert_awaited_once()
            upload.assert_not_awaited()
            poll.assert_awaited_once()
            download.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
