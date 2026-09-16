"""Reuse requires both unchanged evidence and identical reviewer semantics."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from pptagent_runtime import core

spec = importlib.util.spec_from_file_location("reuse_cli", SCRIPTS / "pptagent.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
PASS = {"verdict": "pass", "summary": "Fixture passes", "issues": []}
FAIL = {
    "verdict": "fail",
    "summary": "Clipped",
    "issues": [
        {
            "severity": "major",
            "slide": 1,
            "description": "Clipped",
            "suggested_fix": "Move up",
        }
    ],
}


class ReviewReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        (self.workspace / "task.json").write_text(
            json.dumps({"slides": 2, "aspect_ratio": "16:9", "language": "en"})
        )
        core.scaffold(self.workspace)
        self.image_suffix = b""
        self.config = {
            "mode": "text",
            "visual": {"base_url": "https://example.org/v1", "model": "vision"},
        }

    async def render_fixture(self, workspace: Path) -> dict:
        state = core.load_state(workspace)
        renders = []
        for slide in core.slide_files(workspace):
            image = workspace / "qa" / (slide.stem + ".jpg")
            image.parent.mkdir(exist_ok=True)
            image.write_bytes(slide.read_bytes() + self.image_suffix)
            relative = str(image.relative_to(workspace))
            renders.append(relative)
            state["renders"]["slides"][str(slide.relative_to(workspace))] = {
                "inputs": core.input_snapshot(workspace, [slide]),
                "images": {relative: core.sha256(image)},
            }
        core.save_state(workspace, state)
        return {"ok": True, "renders": renders}

    async def test_only_changed_slide_is_reviewed_again(self) -> None:
        with (
            patch.object(core, "render_slides", side_effect=self.render_fixture),
            patch.object(cli, "review_images", return_value=PASS) as review,
        ):
            await cli.review_slides(self.config, self.workspace)
            slide = self.workspace / "slides/slide02.html"
            slide.write_text(slide.read_text() + "<!-- revised -->")
            result = await cli.review_slides(self.config, self.workspace)
        self.assertEqual(review.call_count, 3)
        self.assertTrue(result["results"][0]["reused"])
        self.assertNotIn("reused", result["results"][1])
        self.assertFalse(
            core.review_gaps(self.workspace, core.slide_files(self.workspace))
        )

    async def test_shared_asset_model_prompt_and_force_invalidate_reuse(self) -> None:
        with (
            patch.object(core, "render_slides", side_effect=self.render_fixture),
            patch.object(cli, "review_images", return_value=PASS) as review,
        ):
            await cli.review_slides(self.config, self.workspace)
            await cli.review_slides(self.config, self.workspace)
            self.assertEqual(review.call_count, 2)
            (self.workspace / "assets/shared.css").write_text("body {color: black}")
            await cli.review_slides(self.config, self.workspace)
            self.assertEqual(review.call_count, 4)
            self.config["visual"]["model"] = "different-vision"
            await cli.review_slides(self.config, self.workspace)
            self.assertEqual(review.call_count, 6)
            with patch("pptagent_runtime.visual.SYSTEM_PROMPT", "Different rubric"):
                await cli.review_slides(self.config, self.workspace)
                self.assertEqual(review.call_count, 8)
                await cli.review_slides(self.config, self.workspace, force=True)
                self.assertEqual(review.call_count, 10)

    async def test_changed_render_is_not_reused(self) -> None:
        with (
            patch.object(core, "render_slides", side_effect=self.render_fixture),
            patch.object(cli, "review_images", return_value=PASS) as review,
        ):
            await cli.review_slides(self.config, self.workspace)
            self.image_suffix = b"different font rendering"
            await cli.review_slides(self.config, self.workspace)
        self.assertEqual(review.call_count, 4)

    async def test_partial_failure_resumes_without_repeating_passed_slide(self) -> None:
        with (
            patch.object(core, "render_slides", side_effect=self.render_fixture),
            patch.object(
                cli, "review_images", side_effect=[PASS, TimeoutError("offline"), PASS]
            ) as review,
        ):
            with self.assertRaises(TimeoutError):
                await cli.review_slides(self.config, self.workspace)
            result = await cli.review_slides(self.config, self.workspace)
        self.assertTrue(result["ok"])
        self.assertEqual(review.call_count, 3)
        self.assertTrue(result["results"][0]["reused"])

    async def test_failed_or_unsigned_reviews_are_not_reused(self) -> None:
        with (
            patch.object(core, "render_slides", side_effect=self.render_fixture),
            patch.object(
                cli, "review_images", side_effect=[FAIL, PASS, PASS, PASS]
            ) as review,
        ):
            await cli.review_slides(self.config, self.workspace)
            core.record_slide_review(
                self.workspace,
                "slides/slide02.html",
                "pass",
                "Legacy fixture",
                [],
                "external-visual",
            )
            result = await cli.review_slides(self.config, self.workspace)
        self.assertTrue(result["ok"])
        self.assertEqual(review.call_count, 4)


if __name__ == "__main__":
    unittest.main()
