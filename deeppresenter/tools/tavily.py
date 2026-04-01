import asyncio
import os
from typing import Any, Literal

import aiohttp
from fake_useragent import UserAgent

from deeppresenter.utils.constants import MAX_RETRY_INTERVAL, RETRY_TIMES
from deeppresenter.utils.log import debug, warning

TAVILY_KEYS = [
    i.strip()
    for i in os.getenv("TAVILY_API_KEY", "").split(",")
    if i.strip().startswith("tvly")
]
TAVILY_API_URL = "https://api.tavily.com/search"

_FAKE_UA = UserAgent()

debug(f"{len(TAVILY_KEYS)} TAVILY keys loaded")


async def _tavily_request(idx: int, params: dict) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "User-Agent": _FAKE_UA.random}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            TAVILY_API_URL, headers=headers, json=params
        ) as response:
            if response.status == 200:
                return await response.json()
            body = await response.text()
            if response.status == 429:
                await asyncio.sleep(MAX_RETRY_INTERVAL)
            else:
                await asyncio.sleep(RETRY_TIMES)
            warning(f"TAVILY Error [{idx:02d}] [{response.status}] body={body}")
            response.raise_for_status()
    raise RuntimeError("TAVILY request failed after retries")


async def _search_with_fallback(**kwargs) -> dict[str, Any]:
    last_error = None
    for idx, api_key in enumerate(TAVILY_KEYS, start=1):
        try:
            params = {**kwargs, "api_key": api_key}
            return await _tavily_request(idx, params)
        except Exception as e:
            warning(f"TAVILY search error with key {api_key[:16]}...: {e}")
            last_error = e
    raise RuntimeError(
        f"TAVILY search failed after {len(TAVILY_KEYS)} retries"
    ) from last_error


def register_tools(mcp) -> None:
    if not TAVILY_KEYS:
        return

    @mcp.tool()
    async def tavily_search_web(
        query: str,
        max_results: int = 3,
        time_range: Literal["month", "year"] | None = None,
    ) -> dict:
        """
        Search the web via Tavily

        Args:
            query: Search keywords
            max_results: Maximum number of search results, default 3
            time_range: Time range filter, "month", "year", or None

        Returns:
            dict: Dictionary containing search results
        """
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "include_images": False,
        }
        if time_range:
            kwargs["time_range"] = time_range

        result = await _search_with_fallback(**kwargs)
        results = [
            {"url": item["url"], "content": item["content"]}
            for item in result.get("results", [])
        ]
        return {"query": query, "total_results": len(results), "results": results}

    @mcp.tool()
    async def tavily_search_images(query: str) -> dict:
        """
        Search for web images via Tavily
        """
        result = await _search_with_fallback(
            query=query,
            max_results=4,
            include_images=True,
            include_image_descriptions=True,
        )
        images = [
            {"url": img["url"], "description": img["description"]}
            for img in result.get("images", [])
        ]
        return {"query": query, "total_results": len(images), "images": images}
