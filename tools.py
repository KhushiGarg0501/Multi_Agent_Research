
import os
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.tools import tool
from tavily import TavilyClient

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise ValueError(
        "TAVILY_API_KEY is missing. Please add it to your .env file."
    )

tavily = TavilyClient(api_key=TAVILY_API_KEY)

TRUSTED_DOMAINS = [
    "arxiv.org",
    "ibm.com",
    "microsoft.com",
    "dora.dev",
    "acm.org",
    "ieee.org",
    "github.blog",
    "mit.edu",
]


def normalize_url(url: str) -> str:
    """Normalize URLs for duplicate detection."""
    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in ("http", "https"):
        return ""

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return ""

    # Remove common tracking parameters and fragments.
    path = parsed.path.rstrip("/")

    return f"{hostname}{path}"


def is_trusted_domain(url: str) -> bool:
    """Check whether the URL belongs to a trusted domain."""
    try:
        hostname = (urlparse(url).hostname or "").lower()

        return any(
            hostname == domain or hostname.endswith("." + domain)
            for domain in TRUSTED_DOMAINS
        )
    except ValueError:
        return False


@tool
def web_search(query: str) -> str:
    """
    Search the web for recent and reliable information.
    Returns unique titles, URLs, and snippets.
    """
    try:
        response = tavily.search(
            query=query,
            max_results=8,
        )

        results = response.get("results", [])
        trusted_results = [
            result for result in results
            if is_trusted_domain(result.get("url", ""))
        ]

        # Prioritize trusted results, then fill remaining slots
        # with other relevant results.
        selected_results = trusted_results[:3]

        for result in results:
            if len(selected_results) >= 3:
                break

            if result not in selected_results:
                selected_results.append(result)

        # Remove duplicate URLs within this search.
        unique_results = []
        seen_urls = set()

        for result in selected_results:
            url = result.get("url", "").strip()
            normalized = normalize_url(url)

            if not normalized or normalized in seen_urls:
                continue

            seen_urls.add(normalized)
            unique_results.append(result)

        if not unique_results:
            return f"No usable search results found for: {query}"

        output = []

        for result in unique_results:
            title = result.get("title", "Untitled")
            url = result.get("url", "")
            snippet = result.get("content", "")[:500]

            output.append(
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Snippet: {snippet}"
            )

        return "\n\n--------\n\n".join(output)

    except Exception as exc:
        return f"Web search failed: {exc}"


@tool
def scrape_url(url: str) -> str:
    """Scrape clean text content from a URL for deeper reading."""
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return "Could not scrape URL: Invalid URL."

        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")

        if "text/html" not in content_type.lower():
            return "Could not scrape URL: The page is not HTML."

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(
            ["script", "style", "nav", "footer", "header", "noscript"]
        ):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        return text[:5000] if text else "No readable text found on the page."

    except Exception as exc:
        return f"Could not scrape URL: {exc}"
