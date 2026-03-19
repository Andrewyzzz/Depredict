"""
YouTube transcript collector for Prediction Market Debater.

Searches YouTube for videos related to a prediction question and extracts
transcripts to use as document context for RAFT-based debate agents.

Usage:
    from youtube_collector import collect_for_question
    docs = collect_for_question("Will Bitcoin reach $100k by end of 2025?")
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from config import MAX_VIDEOS_PER_QUERY


def search_videos(query: str, max_results: int = MAX_VIDEOS_PER_QUERY) -> list[dict]:
    """
    Search YouTube for videos matching the query using yt-dlp.

    Returns list of dicts with video_id, title, channel, duration_seconds.
    """
    results = []
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(
                f"ytsearch{max_results}:{query}", download=False
            )

            for entry in search_results.get("entries", []) or []:
                if not entry:
                    continue
                results.append({
                    "video_id": entry.get("id", ""),
                    "title": entry.get("title", ""),
                    "channel": entry.get("channel", "") or entry.get("uploader", ""),
                    "duration_seconds": int(entry.get("duration") or 0),
                })

    except Exception as e:
        print(f"  YouTube search error for '{query}': {e}")

    return results


def get_transcript(video_id: str) -> str | None:
    """
    Extract transcript/subtitles from a YouTube video.

    Tries English captions first, then auto-generated English.
    Returns the full transcript text, or None if unavailable.
    """
    ytt_api = YouTubeTranscriptApi()
    try:
        transcript = ytt_api.fetch(video_id, languages=["en"])
        full_text = " ".join(entry.text for entry in transcript)
        return full_text
    except Exception:
        try:
            transcript = ytt_api.fetch(video_id, languages=["en-US", "en-GB"])
            full_text = " ".join(entry.text for entry in transcript)
            return full_text
        except Exception:
            return None


def collect_for_question(
    question: str,
    search_queries: list[str] | None = None,
    min_duration: int = 120,
    max_docs: int = 10,
) -> list[dict]:
    """
    Collect YouTube transcripts related to a prediction market question.

    Args:
        question: The prediction question (used as default search query).
        search_queries: Optional list of custom search queries. If None,
            generates queries from the question automatically.
        min_duration: Minimum video duration in seconds (skip short clips).
        max_docs: Maximum number of transcript documents to return.

    Returns:
        List of document dicts with: title, channel, content, url, word_count.
    """
    if search_queries is None:
        search_queries = [question]

    print(f"  [YouTube] Searching for transcripts...")

    seen_ids = set()
    candidates = []

    for query in search_queries:
        print(f"    Query: '{query[:50]}...'")
        videos = search_videos(query)
        print(f"    Found {len(videos)} videos")

        for video in videos:
            vid_id = video["video_id"]
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)
            if video["duration_seconds"] < min_duration:
                continue
            candidates.append(video)

    # Fetch transcripts in parallel
    docs = []

    def _fetch_one(video):
        text = get_transcript(video["video_id"])
        if text is None:
            return None
        return {
            "title": video["title"],
            "channel": video["channel"],
            "content": text,
            "url": f"https://www.youtube.com/watch?v={video['video_id']}",
            "word_count": len(text.split()),
            "duration_seconds": video["duration_seconds"],
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, v): v for v in candidates}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                docs.append(result)
                print(f"      Collected: {result['title'][:50]}... ({result['word_count']} words)")
                if len(docs) >= max_docs:
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break

    # Sort by word count descending (longer = deeper analysis)
    docs.sort(key=lambda d: d["word_count"], reverse=True)

    print(f"  [YouTube] Collected {len(docs)} transcripts")
    return docs
