"""
Information partitioning for multi-agent prediction systems.

Splits retrieved documents into shared (common knowledge) and private
(agent-specific) subsets to create genuine information asymmetry.

This is critical for mechanism design to work: if all agents see identical
information, their predictions converge and weighting doesn't matter.
With private information, agents have genuinely different knowledge bases,
making principled aggregation (LMSR, BTS) more valuable.

Partitioning strategy:
  - Shared pool: top-k most relevant docs (high word count) seen by ALL agents
  - Private pool: remaining docs distributed round-robin to individual agents
  - Each agent sees: shared docs + their private docs
  - No agent sees ALL documents (information asymmetry)
"""

import random
from ..config import Config


def partition_documents(
    all_docs: list[dict],
    agent_names: list[str],
    shared_ratio: float = Config.INFO_PARTITION_SHARED_RATIO,
    private_per_agent: int = Config.INFO_PARTITION_PRIVATE_COUNT,
) -> dict[str, list[dict]]:
    """
    Partition documents into agent-specific views.

    Args:
        all_docs: All retrieved documents, sorted by relevance (word count desc).
        agent_names: List of agent names.
        shared_ratio: Fraction of docs visible to all agents.
        private_per_agent: Number of private docs per agent.

    Returns:
        Dict mapping agent_name -> list of docs visible to that agent.
        Also includes "_shared" key for the shared subset.
    """
    if not all_docs:
        return {name: [] for name in agent_names}

    n_total = len(all_docs)
    n_shared = max(1, int(n_total * shared_ratio))

    # Shared: top documents (most relevant/longest)
    shared_docs = all_docs[:n_shared]

    # Private pool: remaining documents
    private_pool = all_docs[n_shared:]
    random.shuffle(private_pool)

    # Distribute private docs round-robin
    agent_private: dict[str, list[dict]] = {name: [] for name in agent_names}
    pool_idx = 0

    for _ in range(private_per_agent):
        for name in agent_names:
            if pool_idx < len(private_pool):
                agent_private[name].append(private_pool[pool_idx])
                pool_idx += 1

    # Build final views: shared + private for each agent
    result = {}
    for name in agent_names:
        agent_docs = shared_docs.copy() + agent_private[name]
        # Mark which are private
        for doc in agent_docs:
            doc = doc.copy()
        result[name] = agent_docs

    result["_shared"] = shared_docs
    result["_stats"] = {
        "total_docs": n_total,
        "shared_count": n_shared,
        "private_pool_size": len(private_pool),
        "private_per_agent": {
            name: len(docs) for name, docs in agent_private.items()
        },
    }

    return result


def format_agent_context(docs: list[dict]) -> str:
    """Format an agent's document view into context text."""
    if not docs:
        return "(No relevant information found. Analyze based on your own knowledge.)"

    parts = []
    for i, d in enumerate(docs, 1):
        parts.append(f"[Document {i}: {d.get('title', 'Untitled')}]\n{d.get('content', '')}")
    return "\n\n---\n\n".join(parts)
