"""
Knowledge-graph entity/relation extraction for prediction market analysis.

Extracts entities, relations, and timeline events from documents using a single
LLM call, then stores them in an in-memory EntityGraph for downstream querying.
"""

import json
import logging
import re
from typing import Any, Optional

from ..config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EntityGraph – lightweight in-memory knowledge graph
# ---------------------------------------------------------------------------

class EntityGraph:
    """
    In-memory knowledge graph storing entities and directed relations.

    Entities are keyed by (lowercased) name for dedup; relations are stored
    as a flat list of directed edges.
    """

    def __init__(self) -> None:
        # name_lower -> {name, type, description, attributes}
        self._entities: dict[str, dict[str, Any]] = {}
        # list of {source, target, relation_type, context}
        self._relations: list[dict[str, str]] = []
        # list of {date, event}
        self._timeline: list[dict[str, str]] = []

    # -- mutation ----------------------------------------------------------

    def add_entity(
        self,
        name: str,
        entity_type: str = "unknown",
        description: str = "",
        **attributes: Any,
    ) -> None:
        """Add or merge an entity into the graph."""
        key = name.strip().lower()
        if key in self._entities:
            # merge: keep richer description, accumulate attributes
            existing = self._entities[key]
            if description and len(description) > len(existing.get("description", "")):
                existing["description"] = description
            existing["attributes"].update(attributes)
        else:
            self._entities[key] = {
                "name": name.strip(),
                "type": entity_type,
                "description": description,
                "attributes": dict(attributes),
            }

    def add_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        context: str = "",
    ) -> None:
        """Add a directed relation between two entities."""
        self._relations.append({
            "source": source.strip(),
            "target": target.strip(),
            "relation_type": relation_type,
            "context": context,
        })
        # Ensure both endpoints exist as entities (minimal stubs)
        for name in (source, target):
            if name.strip().lower() not in self._entities:
                self.add_entity(name)

    def add_timeline_event(self, date: str, event: str) -> None:
        """Add a timeline event."""
        self._timeline.append({"date": date, "event": event})

    # -- query -------------------------------------------------------------

    def get_entity(self, name: str) -> Optional[dict[str, Any]]:
        """Look up a single entity by name (case-insensitive)."""
        return self._entities.get(name.strip().lower())

    def get_related(self, name: str) -> list[dict[str, str]]:
        """Return all relations where *name* is source or target."""
        key = name.strip().lower()
        return [
            r for r in self._relations
            if r["source"].lower() == key or r["target"].lower() == key
        ]

    def query(self, entity_name: str) -> dict[str, Any]:
        """
        Convenience method: return the entity together with all its relations
        and the entities on the other end of those relations.
        """
        entity = self.get_entity(entity_name)
        relations = self.get_related(entity_name)
        key = entity_name.strip().lower()

        # collect neighbour names
        neighbour_keys: set[str] = set()
        for r in relations:
            neighbour_keys.add(r["source"].lower())
            neighbour_keys.add(r["target"].lower())
        neighbour_keys.discard(key)

        neighbours = [
            self._entities[k] for k in neighbour_keys if k in self._entities
        ]

        return {
            "entity": entity,
            "relations": relations,
            "neighbours": neighbours,
        }

    @property
    def entities(self) -> list[dict[str, Any]]:
        return list(self._entities.values())

    @property
    def relations(self) -> list[dict[str, str]]:
        return list(self._relations)

    @property
    def timeline(self) -> list[dict[str, str]]:
        return list(self._timeline)

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the entire graph to a plain dict."""
        return {
            "entities": self.entities,
            "relations": self.relations,
            "timeline": self.timeline,
        }

    def format_for_context(self) -> str:
        """
        Format the graph into structured text suitable for injection into
        debate / analysis prompts.
        """
        lines: list[str] = []

        if self._entities:
            lines.append("=== Key Entities ===")
            for e in self._entities.values():
                desc = f" - {e['description']}" if e.get("description") else ""
                lines.append(f"- {e['name']} ({e['type']}){desc}")
            lines.append("")

        if self._relations:
            lines.append("=== Key Relationships ===")
            for r in self._relations:
                ctx = f"  ({r['context']})" if r.get("context") else ""
                lines.append(
                    f"- {r['source']} --[{r['relation_type']}]--> {r['target']}{ctx}"
                )
            lines.append("")

        if self._timeline:
            lines.append("=== Timeline ===")
            for t in self._timeline:
                lines.append(f"- [{t['date']}] {t['event']}")
            lines.append("")

        return "\n".join(lines) if lines else "(No structured entities extracted)"


# ---------------------------------------------------------------------------
# LLM-based extraction
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
分析以下文档，提取与问题相关的实体和关系。

问题：{question}

文档：
{documents}

请以JSON格式返回：
{{
  "entities": [
    {{"name": "...", "type": "person|org|event|metric|date|location", "description": "一句话描述"}}
  ],
  "relations": [
    {{"source": "entity_name", "target": "entity_name", "relation": "关系类型", "context": "简要说明"}}
  ],
  "timeline": [
    {{"date": "...", "event": "..."}}
  ]
}}

要求：
- 最多提取 15 个实体、10 条关系、8 个时间线事件
- type 只能是 person / org / event / metric / date / location 之一
- 按时间顺序排列 timeline
- 只输出 JSON，不要其他文字"""


def _build_doc_text(documents: list[dict], max_chars: int = 4000) -> str:
    """Concatenate document contents, truncating to *max_chars* total."""
    parts: list[str] = []
    total = 0
    for i, doc in enumerate(documents, 1):
        title = doc.get("title", f"Document {i}")
        content = doc.get("content", "")
        header = f"[Doc {i}] {title}\n"
        remaining = max_chars - total - len(header) - 10  # 10 for separator
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining] + "...[truncated]"
        chunk = header + content
        parts.append(chunk)
        total += len(chunk)
    return "\n\n---\n\n".join(parts)


def _parse_json_response(raw: str) -> dict:
    """
    Robustly parse a JSON object from an LLM response.
    Tries direct parse, code-block extraction, regex, and light cleanup.
    """
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: markdown code block
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: find outermost { … }
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4: light cleanup
    cleaned = raw.strip()
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    cleaned = cleaned.replace("'", '"')
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return {"entities": [], "relations": [], "timeline": []}


def _call_llm(prompt: str, backend: dict) -> str:
    """
    Call the LLM using the appropriate SDK depending on *backend['label']*.

    Returns the raw text response.
    """
    if backend["label"] == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=backend["api_key"])
        resp = client.messages.create(
            model=backend["model"],
            max_tokens=3000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic SDK returns content blocks
        return resp.content[0].text if resp.content else ""
    else:
        from openai import OpenAI

        client = OpenAI(
            api_key=backend["api_key"],
            base_url=backend.get("base_url"),
        )
        resp = client.chat.completions.create(
            model=backend["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )
        return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_entities_from_docs(
    documents: list[dict],
    question: str,
    backend: Optional[dict] = None,
) -> EntityGraph:
    """
    Extract entities, relations, and timeline from *documents* using a single
    LLM call and return a populated :class:`EntityGraph`.

    Parameters
    ----------
    documents:
        List of dicts with at least ``"content"`` (and optionally ``"title"``).
    question:
        The prediction-market question to guide extraction.
    backend:
        Optional backend dict with keys ``api_key``, ``base_url``, ``model``,
        ``label``.  If *None*, the first available backend from
        ``Config.get_available_backends()`` is used.

    Returns
    -------
    EntityGraph
        Populated knowledge graph.
    """
    graph = EntityGraph()

    if not documents:
        return graph

    # Resolve backend
    if backend is None:
        backends = Config.get_available_backends()
        if not backends:
            logger.warning("No LLM backend configured; returning empty graph")
            return graph
        backend = backends[0]

    # Build prompt
    doc_text = _build_doc_text(documents, max_chars=4000)
    prompt = _EXTRACTION_PROMPT.format(question=question, documents=doc_text)

    # Call LLM
    try:
        raw = _call_llm(prompt, backend)
    except Exception as e:
        logger.error("Entity extraction LLM call failed: %s", e)
        return graph

    # Parse response
    data = _parse_json_response(raw)

    # Populate graph – entities
    for e in data.get("entities", []):
        if not isinstance(e, dict) or "name" not in e:
            continue
        graph.add_entity(
            name=str(e["name"]),
            entity_type=str(e.get("type", "unknown")),
            description=str(e.get("description", "")),
        )

    # Populate graph – relations
    for r in data.get("relations", []):
        if not isinstance(r, dict):
            continue
        source = str(r.get("source", ""))
        target = str(r.get("target", ""))
        if not source or not target:
            continue
        graph.add_relation(
            source=source,
            target=target,
            relation_type=str(r.get("relation", "")),
            context=str(r.get("context", "")),
        )

    # Populate graph – timeline
    for t in data.get("timeline", []):
        if not isinstance(t, dict) or "event" not in t:
            continue
        graph.add_timeline_event(
            date=str(t.get("date", "unknown")),
            event=str(t.get("event", "")),
        )

    logger.info(
        "Entity extraction complete: %d entities, %d relations, %d timeline events",
        len(graph.entities),
        len(graph.relations),
        len(graph.timeline),
    )
    return graph
