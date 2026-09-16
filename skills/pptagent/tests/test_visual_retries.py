"""Network retries must not hide authentication or review-format failures."""

from __future__ import annotations

import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pptagent_runtime.visual import _request_review


class VisualRetryTests(unittest.TestCase):
    def test_transient_disconnect_is_retried(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"choices": []}'
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=[urllib.error.URLError("disconnect"), response],
            ) as send,
            patch("pptagent_runtime.visual.time.sleep") as sleep,
        ):
            self.assertEqual(
                _request_review(urllib.request.Request("https://example.org"), 5),
                {"choices": []},
            )
        self.assertEqual(send.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_retry_budget_is_bounded(self) -> None:
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("disconnect"),
            ) as send,
            patch("pptagent_runtime.visual.time.sleep"),
            self.assertRaises(urllib.error.URLError),
        ):
            _request_review(urllib.request.Request("https://example.org"), 5)
        self.assertEqual(send.call_count, 3)

    def test_authentication_and_invalid_json_are_not_retried(self) -> None:
        auth = urllib.error.HTTPError(
            "https://example.org", 401, "Unauthorized", {}, None
        )
        with (
            patch("urllib.request.urlopen", side_effect=auth) as send,
            self.assertRaises(urllib.error.HTTPError),
        ):
            _request_review(urllib.request.Request("https://example.org"), 5)
        send.assert_called_once()
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"invalid JSON"
        with (
            patch("urllib.request.urlopen", return_value=response) as send,
            self.assertRaises(json.JSONDecodeError),
        ):
            _request_review(urllib.request.Request("https://example.org"), 5)
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
