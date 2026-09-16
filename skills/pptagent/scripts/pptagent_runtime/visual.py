from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import visual_settings

SYSTEM_PROMPT = (
    "You are a strict presentation visual reviewer. Judge only visible audience impact. "
    "Return one JSON object with verdict (pass, fail, or unjudgeable), summary, and "
    "issues. Each issue must contain severity (blocker, major, or minor), slide (a "
    "positive JSON integer, not a string; use the slide number from the context or "
    "contact sheet), description (a nonempty string), and suggested_fix (a nonempty "
    "string). Use an empty issues array when no issues are visible. Do not return "
    "Markdown or additional text. Fail only for blocker or major issues such as clipping, "
    "overlap, unreadable text, broken images, severe imbalance, or materially "
    "inconsistent design. Do not fact-check dates, citations, or technical claims; "
    "the host verifies these against sources. Do not infer today's date or fail "
    "a slide because a displayed date seems to be in the future."
)


def reviewer_id(config: dict[str, Any], context: str) -> str:
    """Identify review semantics without persisting credentials."""
    settings = visual_settings(config)
    payload = [settings["base_url"], settings["model"], SYSTEM_PROMPT, context, 0]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def validate_review(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("verdict") not in {
        "pass",
        "fail",
        "unjudgeable",
    }:
        raise ValueError("review must contain a valid verdict")
    if not isinstance(payload.get("summary"), str) or not payload["summary"].strip():
        raise ValueError("review summary must be nonempty text")
    if not isinstance(payload.get("issues"), list):
        raise TypeError("review issues must be a list")
    for issue in payload["issues"]:
        if not isinstance(issue, dict) or issue.get("severity") not in {
            "blocker",
            "major",
            "minor",
        }:
            raise ValueError("each issue must contain a valid severity")
        if type(issue.get("slide")) is not int or issue["slide"] < 1:
            raise ValueError("each issue must identify a positive slide number")
        if any(
            not isinstance(issue.get(key), str) or not issue[key].strip()
            for key in ("description", "suggested_fix")
        ):
            raise ValueError("each issue must contain a description and suggested_fix")
        if payload["verdict"] == "pass" and issue["severity"] in {"blocker", "major"}:
            raise ValueError("a review with blocker or major issues cannot pass")
    return {**payload, "ok": payload["verdict"] == "pass"}


def _parse_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    return validate_review(json.loads(fenced.group(1) if fenced else candidate))


def _request_review(request: urllib.request.Request, timeout: int) -> dict[str, Any]:
    """Retry transient transport failures per image, not the entire deck."""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == 2 or (
                isinstance(exc, urllib.error.HTTPError)
                and exc.code not in {502, 503, 504}
            ):
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def review_images(
    config: dict[str, Any], image_paths: list[Path], context: str
) -> dict[str, Any]:
    settings = visual_settings(config)
    if not settings["base_url"] or not settings["model"] or not settings["api_key"]:
        raise ValueError(
            "visual review requires visual.base_url, visual.model, and "
            + settings["api_key_env"]
        )
    if not image_paths:
        raise ValueError("visual review requires at least one image")
    content: list[dict[str, Any]] = [{"type": "text", "text": context}]
    for path in image_paths:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            }
        )
    body = json.dumps(
        {
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        settings["base_url"] + "/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json",
        },
    )
    payload = _request_review(request, settings["timeout_seconds"])
    choice = payload["choices"][0]
    if choice.get("finish_reason") in {"length", "content_filter"}:
        raise ValueError(f"Incomplete visual review: {choice['finish_reason']}")
    message = choice["message"]["content"]
    if isinstance(message, list):
        message = "\n".join(
            str(item.get("text") or "") for item in message if isinstance(item, dict)
        )
    return _parse_json(str(message))
