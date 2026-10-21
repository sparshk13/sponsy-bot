"""Tavily search client enforcing BUD-05 and SEC-18."""

from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass
class SearchResult:
    url: str
    content: str
    title: str = ""


class TavilySearchClient:
    """Tavily search client with basic depth and 10-second timeout (BUD-05, SEC-18)."""

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not settings.tavily_api_key:
            return []

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results: list[SearchResult] = []
            for item in data.get("results", []):
                results.append(
                    SearchResult(
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        title=item.get("title", ""),
                    )
                )
            return results


search_client = TavilySearchClient()
