# -*- coding: utf-8 -*-
"""
Tavily 网页搜索
当本地 RAG 检索不足时，调用 Tavily 补充网络资料
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    使用 Tavily 搜索网页。

    Returns:
        与 RAG docs 同构: [{"content": str, "title": str, "source_file": str}, ...]
        source_file 为 URL
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            topic="general",
        )
        results = response.get("results", [])
        return [
            {
                "content": r.get("content", ""),
                "title": r.get("title", "未知"),
                "source_file": r.get("url", ""),
            }
            for r in results
            if r.get("content")
        ]
    except Exception:
        return []
