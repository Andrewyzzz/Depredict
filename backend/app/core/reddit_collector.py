"""
Reddit post collector for Prediction Market Debater.

Uses Reddit's public JSON API (no authentication required) to search for
posts related to a prediction question across relevant subreddits.

Usage:
    from ..core.reddit_collector import collect_reddit_posts
    posts = collect_reddit_posts("Will Bitcoin reach $100k by end of 2025?", category="crypto")
"""

import time
import requests

from ..config import Config

# Category-specific subreddits for targeted search
CATEGORY_SUBREDDITS = {
    "crypto": ["cryptocurrency", "bitcoin"],
    "politics": ["politics", "geopolitics"],
    "sports": ["sports", "sportsbook"],
    "ai_tech": ["artificial", "machinelearning"],
    "general": ["news", "worldnews"],
}


def _reddit_get(url: str, params: dict | None = None) -> dict | None:
    """Make a GET request to Reddit's JSON API with rate-limit-friendly headers."""
    headers = {"User-Agent": Config.REDDIT_USER_AGENT}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 429:
            print("  [Reddit] Rate limited, waiting 3s...")
            time.sleep(3)
            resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [Reddit] Request error for {url}: {e}")
        return None


def _extract_posts(data: dict, max_posts: int) -> list[dict]:
    """Extract post dicts from a Reddit JSON listing response."""
    posts = []
    if not data or "data" not in data:
        return posts

    for child in data["data"].get("children", []):
        if len(posts) >= max_posts:
            break
        post_data = child.get("data", {})
        if not post_data:
            continue

        title = post_data.get("title", "")
        selftext = post_data.get("selftext", "")
        # Use selftext if available; otherwise just the title
        content = selftext.strip() if selftext.strip() else title
        # Truncate very long posts
        if len(content) > 5000:
            content = content[:5000] + "..."

        url = post_data.get("url", "")
        permalink = post_data.get("permalink", "")
        if permalink and not url.startswith("https://www.reddit.com"):
            url = f"https://www.reddit.com{permalink}"

        posts.append({
            "title": title,
            "content": content,
            "url": url,
            "source": "reddit",
            "subreddit": post_data.get("subreddit", ""),
            "score": int(post_data.get("score", 0)),
            "word_count": len(content.split()),
        })

    return posts


def _search_subreddit(subreddit: str, query: str, max_posts: int) -> list[dict]:
    """Search a specific subreddit for posts matching the query."""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "sort": "relevance",
        "limit": max_posts,
        "restrict_sr": "on",
        "t": "month",  # last month for recency
    }
    data = _reddit_get(url, params)
    # Rate limiting: 1 request per 2 seconds
    time.sleep(2)
    return _extract_posts(data, max_posts) if data else []


def _search_global(query: str, max_posts: int) -> list[dict]:
    """Search all of Reddit for posts matching the query."""
    url = "https://www.reddit.com/search.json"
    params = {
        "q": query,
        "sort": "relevance",
        "limit": max_posts,
        "t": "month",
    }
    data = _reddit_get(url, params)
    time.sleep(2)
    return _extract_posts(data, max_posts) if data else []


def collect_reddit_posts(
    question: str,
    category: str | None = None,
    max_posts: int = 10,
) -> list[dict]:
    """
    Collect Reddit posts related to a prediction market question.

    Args:
        question: The prediction question to search for.
        category: Optional category for targeted subreddit search.
            One of: crypto, politics, sports, ai_tech, general.
        max_posts: Maximum number of posts to return.

    Returns:
        List of post dicts with: title, content, url, source, subreddit, score, word_count.
    """
    print(f"  [Reddit] Searching for posts...")
    all_posts = []
    seen_urls = set()

    def _add_posts(posts):
        for p in posts:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                all_posts.append(p)

    try:
        # 1. Global search
        global_posts = _search_global(question, max_posts=20)
        _add_posts(global_posts)
        print(f"    Global search: {len(global_posts)} posts")

        # 2. Category-specific subreddit searches
        subreddits = CATEGORY_SUBREDDITS.get(category, []) if category else []
        # Also always check general news subreddits
        if category != "general":
            subreddits = subreddits + ["news", "worldnews"]

        for sub in subreddits:
            sub_posts = _search_subreddit(sub, question, max_posts=10)
            _add_posts(sub_posts)
            print(f"    r/{sub}: {len(sub_posts)} posts")

    except Exception as e:
        print(f"  [Reddit] Collection error: {e}")
        return []

    # Sort by score (most upvoted = community-validated relevance)
    all_posts.sort(key=lambda p: p["score"], reverse=True)

    # Return top N
    result = all_posts[:max_posts]
    print(f"  [Reddit] Collected {len(result)} posts total")
    return result
