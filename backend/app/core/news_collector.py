"""
News collector for Prediction Market Debater.

Aggregates news from multiple free sources:
- Google News RSS feed
- DuckDuckGo HTML search (titles + snippets)

Tavily is handled separately in the retriever (already integrated).

Usage:
    from ..core.news_collector import collect_news
    articles = collect_news("Will Bitcoin reach $100k by end of 2025?")
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests


def _fetch_google_news_rss(query: str, max_articles: int = 10) -> list[dict]:
    """
    Fetch news articles from Google News RSS feed.

    Args:
        query: Search query string.
        max_articles: Maximum number of articles to return.

    Returns:
        List of article dicts.
    """
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en"

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "prediction-market-debater/1.0"
        })
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        articles = []

        # RSS structure: rss > channel > item
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            if len(articles) >= max_articles:
                break

            title = item.findtext("title", "")
            link = item.findtext("link", "")
            description = item.findtext("description", "")
            pub_date = item.findtext("pubDate", "")

            # Google News descriptions often contain HTML; strip tags
            clean_desc = re.sub(r"<[^>]+>", "", description).strip()
            content = f"{title}. {clean_desc}" if clean_desc else title

            articles.append({
                "title": title,
                "content": content,
                "url": link,
                "source": "news_rss",
                "published": pub_date,
                "word_count": len(content.split()),
            })

        return articles

    except Exception as e:
        print(f"  [Google News RSS] Error: {e}")
        return []


def _fetch_duckduckgo_news(query: str, max_articles: int = 10) -> list[dict]:
    """
    Fetch news snippets from DuckDuckGo HTML search.

    Uses simple regex parsing to extract titles and snippets.
    No external HTML parsing dependency required.

    Args:
        query: Search query string.
        max_articles: Maximum number of articles to return.

    Returns:
        List of article dicts.
    """
    encoded_query = quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "prediction-market-debater/1.0"
        })
        resp.raise_for_status()
        html = resp.text

        articles = []

        # Extract result blocks: each result has a link and snippet
        # DuckDuckGo HTML format: <a class="result__a" href="...">title</a>
        # and <a class="result__snippet" ...>snippet text</a>

        # Extract titles and URLs
        title_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        titles = re.findall(title_pattern, html, re.DOTALL)

        # Extract snippets
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'
        snippets = re.findall(snippet_pattern, html, re.DOTALL)

        for i in range(min(len(titles), max_articles)):
            raw_url, raw_title = titles[i]
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

            content = f"{title}. {snippet}" if snippet else title

            # DuckDuckGo redirects through their own URL; extract actual URL
            # Format: //duckduckgo.com/l/?uddg=ENCODED_URL&...
            actual_url = raw_url
            uddg_match = re.search(r'uddg=([^&]+)', raw_url)
            if uddg_match:
                from urllib.parse import unquote
                actual_url = unquote(uddg_match.group(1))

            articles.append({
                "title": title,
                "content": content,
                "url": actual_url,
                "source": "duckduckgo",
                "published": "",
                "word_count": len(content.split()),
            })

        return articles

    except Exception as e:
        print(f"  [DuckDuckGo] Error: {e}")
        return []


def collect_news(
    question: str,
    max_articles: int = 10,
) -> list[dict]:
    """
    Collect news articles from multiple free sources.

    Args:
        question: The prediction question to search for.
        max_articles: Maximum number of articles to return.

    Returns:
        List of article dicts with: title, content, url, source, published, word_count.
    """
    print(f"  [News] Collecting from RSS and web sources...")
    all_articles = []
    seen_urls = set()

    def _add_articles(articles):
        for a in articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                all_articles.append(a)

    # 1. Google News RSS
    try:
        rss_articles = _fetch_google_news_rss(question, max_articles=max_articles)
        _add_articles(rss_articles)
        print(f"    Google News RSS: {len(rss_articles)} articles")
    except Exception as e:
        print(f"    Google News RSS failed: {e}")

    # 2. DuckDuckGo HTML search
    try:
        ddg_articles = _fetch_duckduckgo_news(question, max_articles=max_articles)
        _add_articles(ddg_articles)
        print(f"    DuckDuckGo: {len(ddg_articles)} articles")
    except Exception as e:
        print(f"    DuckDuckGo failed: {e}")

    # Sort by word count descending
    all_articles.sort(key=lambda a: a["word_count"], reverse=True)

    result = all_articles[:max_articles]
    print(f"  [News] Collected {len(result)} articles total")
    return result
