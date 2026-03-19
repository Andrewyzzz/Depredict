"""
Retriever for prediction market questions.

Uses YouTube transcripts as the primary data source (like the NBA project),
with Tavily news as an optional supplement.
Applies RAFT-inspired mixing of relevant + distractor documents.
"""

import random

from config import TAVILY_API_KEY, YOUTUBE_ORACLE_COUNT, YOUTUBE_MAX_TRANSCRIPT_CHARS
from youtube_collector import collect_for_question


class NewsRetriever:
    """Retrieves and formats context documents for prediction questions."""

    def __init__(self):
        self.tavily_client = None
        if TAVILY_API_KEY:
            from tavily import TavilyClient
            self.tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

    def retrieve(
        self,
        question: str,
        search_queries: list[str] | None = None,
        oracle_count: int = YOUTUBE_ORACLE_COUNT,
    ) -> dict:
        """
        Retrieve context documents for a prediction market question.

        Primary source: YouTube transcripts (expert analysis, deeper content).
        Supplement: Tavily news (if configured).

        RAFT approach: top documents by word count are marked as "oracle",
        the rest are "distractors". All are mixed and shuffled.

        Args:
            question: The prediction question.
            search_queries: Optional custom YouTube search queries.
            oracle_count: Number of top docs to treat as oracle.

        Returns:
            Dict with relevant, distractors, mixed_docs, context_text, oracle_indices.
        """
        all_docs = []

        # 1. YouTube transcripts (primary source)
        yt_docs = collect_for_question(
            question, search_queries=search_queries
        )
        for doc in yt_docs:
            # Truncate very long transcripts
            content = doc["content"]
            if len(content) > YOUTUBE_MAX_TRANSCRIPT_CHARS:
                content = content[:YOUTUBE_MAX_TRANSCRIPT_CHARS] + "..."
            all_docs.append({
                "title": f"[YouTube] {doc['title']}",
                "content": content,
                "url": doc["url"],
                "source": "youtube",
                "word_count": doc["word_count"],
            })

        # 2. Tavily news (supplement)
        if self.tavily_client:
            try:
                tavily_results = self.tavily_client.search(
                    query=question, max_results=5
                )
                for r in tavily_results.get("results", []):
                    all_docs.append({
                        "title": f"[News] {r.get('title', '')}",
                        "content": r.get("content", ""),
                        "url": r.get("url", ""),
                        "source": "tavily",
                        "word_count": len(r.get("content", "").split()),
                    })
            except Exception as e:
                print(f"  [Tavily] Search error: {e}")

        if not all_docs:
            return {
                "relevant": [],
                "distractors": [],
                "mixed_docs": [],
                "context_text": "(未找到相关信息。Agent 将仅基于自身知识进行分析。)",
                "oracle_indices": [],
            }

        # 3. Rank by word count (longer = deeper analysis = more likely relevant)
        all_docs.sort(key=lambda d: d["word_count"], reverse=True)

        # 4. Split into oracle (top-k) + distractors (rest)
        relevant = all_docs[:oracle_count]
        distractors = all_docs[oracle_count:]

        # 5. RAFT: mix with oracle markers, shuffle
        mixed_docs = []
        for doc in relevant:
            mixed_docs.append({**doc, "is_oracle": True})
        for doc in distractors:
            mixed_docs.append({**doc, "is_oracle": False})
        random.shuffle(mixed_docs)

        oracle_indices = [i for i, d in enumerate(mixed_docs) if d["is_oracle"]]

        print(
            f"  [Retriever] {len(yt_docs)} YouTube transcripts + "
            f"{len(all_docs) - len(yt_docs)} news articles | "
            f"{len(relevant)} oracle, {len(distractors)} distractors"
        )

        return {
            "relevant": relevant,
            "distractors": distractors,
            "mixed_docs": mixed_docs,
            "context_text": self._format_context(mixed_docs),
            "oracle_indices": oracle_indices,
        }

    def _format_context(self, docs: list) -> str:
        """Format documents into a numbered text block for prompt injection."""
        if not docs:
            return "(未找到相关信息)"

        parts = []
        for i, d in enumerate(docs, 1):
            # Show source type and truncate content for display
            parts.append(f"[文档 {i}: {d['title']}]\n{d['content']}")
        return "\n\n---\n\n".join(parts)
