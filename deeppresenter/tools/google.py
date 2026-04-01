import os
from typing import Any, Literal

import aiohttp

from deeppresenter.utils.log import debug, warning

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
SERPAPI_URL = "https://serpapi.com/search"

if SERPAPI_KEY:
    debug("SerpAPI configured")


async def _serpapi_request(params: dict[str, Any]) -> dict[str, Any]:
    params = {**params, "api_key": SERPAPI_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(SERPAPI_URL, params=params) as response:
            if response.status == 200:
                return await response.json()
            body = await response.text()
            warning(f"SERPAPI Error [{response.status}] body={body}")
            response.raise_for_status()
    raise RuntimeError("SerpAPI request failed")


def register_tools(mcp) -> None:
    if not SERPAPI_KEY:
        return

    @mcp.tool()
    async def google_search_web(
        query: str,
        max_results: int = 3,
        time_range: Literal["month", "year"] | None = None,
    ) -> dict:
        """
        Search the web via Google (SerpAPI)

        Args:
            query: Search keywords
            max_results: Maximum number of search results, default 3
            time_range: Time range filter, "month", "year", or None

        Returns:
            dict: Dictionary containing search results
        """
        params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "num": max_results,
        }
        if time_range == "month":
            params["tbs"] = "qdr:m"
        elif time_range == "year":
            params["tbs"] = "qdr:y"

        result = await _serpapi_request(params)
        results = [
            {"url": item["link"], "content": item.get("snippet", "")}
            for item in result.get("organic_results", [])
        ]
        return {"query": query, "total_results": len(results), "results": results}

    @mcp.tool()
    async def google_search_images(query: str) -> dict:
        """
        Search for web images via Google (SerpAPI)
        """
        params: dict[str, Any] = {
            "engine": "google_images",
            "q": query,
            "num": 4,
        }
        result = await _serpapi_request(params)
        images = [
            {
                "url": item["original"],
                "description": item.get("title", query),
            }
            for item in result.get("images_results", [])[:4]
        ]
        return {"query": query, "total_results": len(images), "images": images}
