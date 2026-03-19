"""
Retriever for prediction market questions.

Uses multiple data sources in parallel:
- YouTube transcripts (expert analysis, deeper content)
- Tavily news (if configured)
- Reddit posts (community discussion, sentiment)
- Google News RSS + DuckDuckGo (free news aggregation)

Returns all relevant documents sorted by word count (descending),
deduplicated by URL.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import Config
from ..core.youtube_collector import collect_for_question
from ..core.reddit_collector import collect_reddit_posts
from ..core.news_collector import collect_news


class NewsRetriever:
    """Retrieves and formats context documents for prediction questions."""

    def __init__(self):
        self.tavily_client = None
        if Config.TAVILY_API_KEY:
            from tavily import TavilyClient
            self.tavily_client = TavilyClient(api_key=Config.TAVILY_API_KEY)

    def _collect_youtube(self, question: str, search_queries: list[str] | None) -> list[dict]:
        """Collect YouTube transcripts and normalize to common doc format."""
        docs = []
        try:
            yt_docs = collect_for_question(question, search_queries=search_queries)
            for doc in yt_docs:
                content = doc["content"]
                if len(content) > Config.YOUTUBE_MAX_TRANSCRIPT_CHARS:
                    content = content[:Config.YOUTUBE_MAX_TRANSCRIPT_CHARS] + "..."
                docs.append({
                    "title": f"[YouTube] {doc['title']}",
                    "content": content,
                    "url": doc["url"],
                    "source": "youtube",
                    "word_count": len(content.split()),
                })
        except Exception as e:
            print(f"  [YouTube] Collection error: {e}")
        return docs

    def _collect_tavily(self, question: str) -> list[dict]:
        """Collect Tavily news results."""
        docs = []
        if not self.tavily_client:
            return docs
        try:
            tavily_results = self.tavily_client.search(
                query=question, max_results=5
            )
            for r in tavily_results.get("results", []):
                docs.append({
                    "title": f"[News] {r.get('title', '')}",
                    "content": r.get("content", ""),
                    "url": r.get("url", ""),
                    "source": "tavily",
                    "word_count": len(r.get("content", "").split()),
                })
        except Exception as e:
            print(f"  [Tavily] Search error: {e}")
        return docs

    def _collect_reddit(self, question: str, category: str | None = None) -> list[dict]:
        """Collect Reddit posts and normalize to common doc format."""
        docs = []
        try:
            posts = collect_reddit_posts(question, category=category, max_posts=10)
            for post in posts:
                docs.append({
                    "title": f"[Reddit] {post['title']}",
                    "content": post["content"],
                    "url": post["url"],
                    "source": "reddit",
                    "word_count": post["word_count"],
                })
        except Exception as e:
            print(f"  [Reddit] Collection error: {e}")
        return docs

    def _collect_news(self, question: str) -> list[dict]:
        """Collect news from RSS and web sources."""
        docs = []
        try:
            articles = collect_news(question, max_articles=10)
            for article in articles:
                source_label = "Google News" if article["source"] == "news_rss" else "DuckDuckGo"
                docs.append({
                    "title": f"[{source_label}] {article['title']}",
                    "content": article["content"],
                    "url": article["url"],
                    "source": article["source"],
                    "word_count": article["word_count"],
                })
        except Exception as e:
            print(f"  [News] Collection error: {e}")
        return docs

    def retrieve(
        self,
        question: str,
        search_queries: list[str] | None = None,
        category: str | None = None,
    ) -> dict:
        """
        Retrieve context documents for a prediction market question.

        Runs all data sources in parallel:
        - YouTube transcripts
        - Tavily news (if configured)
        - Reddit posts
        - Google News RSS + DuckDuckGo

        Args:
            question: The prediction question.
            search_queries: Optional custom YouTube search queries.
            category: Optional category for Reddit subreddit targeting
                (crypto, politics, sports, ai_tech, general).

        Returns:
            Dict with documents, context_text, sources, source_stats.
        """
        all_docs = []
        source_stats = {}

        # Run all collectors in parallel
        with ThreadPoolExecutor(max_workers=4) as pool:
            future_youtube = pool.submit(self._collect_youtube, question, search_queries)
            future_tavily = pool.submit(self._collect_tavily, question)
            future_reddit = pool.submit(self._collect_reddit, question, category)
            future_news = pool.submit(self._collect_news, question)

            futures = {
                future_youtube: "youtube",
                future_tavily: "tavily",
                future_reddit: "reddit",
                future_news: "news",
            }

            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    docs = future.result()
                    all_docs.extend(docs)
                    source_stats[source_name] = len(docs)
                except Exception as e:
                    print(f"  [{source_name}] Unexpected error: {e}")
                    source_stats[source_name] = 0

        if not all_docs:
            return {
                "documents": [],
                "context_text": "(未找到相关信息。Agent 将仅基于自身知识进行分析。)",
                "sources": [],
                "source_stats": source_stats,
            }

        # Deduplicate by URL
        seen_urls = set()
        unique_docs = []
        for doc in all_docs:
            url = doc.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            unique_docs.append(doc)

        # Sort by word_count descending (most substantive first)
        unique_docs.sort(key=lambda d: d["word_count"], reverse=True)

        # Limit to top N
        max_docs = Config.MAX_RETRIEVAL_DOCS
        unique_docs = unique_docs[:max_docs]

        sources = [{"title": d["title"], "url": d["url"], "source": d["source"]} for d in unique_docs]

        # Print summary
        stats_str = " + ".join(f"{v} {k}" for k, v in source_stats.items() if v > 0)
        print(
            f"  [Retriever] {stats_str} | "
            f"{len(unique_docs)} documents after dedup (max {max_docs})"
        )

        return {
            "documents": unique_docs,
            "context_text": self._format_context(unique_docs),
            "sources": sources,
            "source_stats": source_stats,
        }

    def _format_context(self, docs: list) -> str:
        """Format documents into a numbered text block for prompt injection."""
        if not docs:
            return "(未找到相关信息)"

        parts = []
        for i, d in enumerate(docs, 1):
            parts.append(f"[文档 {i}: {d['title']}]\n{d['content']}")
        return "\n\n---\n\n".join(parts)
