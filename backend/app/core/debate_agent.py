"""
Debate agent for prediction market questions.

Each DebateAgent has a distinct persona (bull/bear/neutral) and participates in
a 3-round debate to estimate the probability of a YES/NO prediction market outcome.
Supports multiple LLM backends (DeepSeek, OpenAI, Anthropic, etc.).
"""

import os
import re

from openai import OpenAI

from ..config import Config


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = os.path.join(Config.PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class DebateAgent:
    """A debate agent with a specific analytical stance and LLM backend."""

    def __init__(
        self,
        name: str,
        stance: str,
        description: str,
        style: str,
        backend: dict | None = None,
    ):
        self.name = name
        self.stance = stance
        self.description = description
        self.style = style

        # Multi-model support: use provided backend or default to DeepSeek
        if backend:
            self.model = backend["model"]
            self.backend_label = backend["label"]
        else:
            backend = {
                "api_key": Config.DEEPSEEK_API_KEY,
                "base_url": Config.DEEPSEEK_BASE_URL,
                "model": Config.DEEPSEEK_MODEL,
                "label": "deepseek",
            }
            self.model = backend["model"]
            self.backend_label = backend["label"]

        # Anthropic uses its own SDK; everything else uses OpenAI-compatible client
        self._is_anthropic = self.backend_label == "anthropic"
        if self._is_anthropic:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=backend["api_key"])
            self.client = None
        else:
            self.client = OpenAI(api_key=backend["api_key"], base_url=backend["base_url"])
            self._anthropic_client = None

        self._last_round1: dict = {}

    def _chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        """Unified chat completion with retry on rate limits and timeout."""
        import time

        max_retries = 3
        timeout = 90  # seconds per attempt

        for attempt in range(max_retries):
            try:
                if self._is_anthropic:
                    response = self._anthropic_client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        system=system,
                        messages=[{"role": "user", "content": user}],
                        timeout=timeout,
                    )
                    return response.content[0].text
                else:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        timeout=timeout,
                    )
                    return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "rate" in err_str.lower()
                is_timeout = "timeout" in err_str.lower() or "timed out" in err_str.lower()
                if (is_rate_limit or is_timeout) and attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    reason = "rate limited" if is_rate_limit else "timed out"
                    print(f"  [{self.name}] {reason}, retrying in {wait}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                raise

    def _build_system_prompt(self, context_text: str) -> str:
        """Build system prompt by injecting persona and RAG context into template."""
        template = _load_prompt("agent_system.txt")
        return template.format(
            name=self.name,
            description=self.description,
            stance=self.stance,
            style=self.style,
            context=context_text,
        )

    def predict(self, question: str, context_text: str) -> dict:
        """
        Round 1: Independent prediction.

        Returns dict with agent_name, stance, probability, reasoning, raw_response.
        """
        system = self._build_system_prompt(context_text)
        user_prompt = f"""请分析以下预测市场问题并给出概率估计：

问题：{question}

请按以下结构分析：
1. 支持（YES）的论据（至少 3 条，引用具体数据和事实）
2. 反对（NO）的论据（至少 3 条，引用具体数据和事实）
3. 综合分析（权衡以上因素）
4. 最终概率估计

请严格按以下格式回答：

REASONING: <你的分析>

PREDICTION: <0-100 的数字>%"""

        text = self._chat(system, user_prompt, max_tokens=2048)

        result = self._parse_round1_response(text)
        self._last_round1 = result
        return result

    def debate(self, question: str, context_text: str, other_results: list[dict]) -> dict:
        """
        Round 2: Cross-rebuttal. Review other agents' Round 1 predictions and respond.

        Args:
            question: The prediction question.
            context_text: RAG context.
            other_results: List of other agents' Round 1 results.

        Returns dict with rebuttals, reasoning, probability.
        """
        template = _load_prompt("debate_round2.txt")

        # Format other agents' predictions
        other_parts = []
        rebuttal_template_parts = []
        for other in other_results:
            prob_str = f"{other['probability']}%" if other["probability"] is not None else "N/A"
            other_parts.append(
                f"--- {other['agent_name']} ({other['stance']}) ---\n"
                f"推理: {other['reasoning']}\n"
                f"预测: {prob_str}"
            )
            rebuttal_template_parts.append(
                f"Re: {other['agent_name']}: <你的具体反驳>"
            )

        # Format own Round 1 prediction
        own_prob_str = (
            f"{self._last_round1['probability']}%"
            if self._last_round1.get("probability") is not None
            else "N/A"
        )
        own_prediction = (
            f"推理: {self._last_round1.get('reasoning', '')}\n"
            f"预测: {own_prob_str}"
        )

        rebuttal_template = "\n".join(rebuttal_template_parts)

        user_prompt = template.format(
            name=self.name,
            question=question,
            other_predictions="\n\n".join(other_parts),
            own_prediction=own_prediction,
            rebuttal_template=rebuttal_template,
        )

        system = self._build_system_prompt(context_text)

        text = self._chat(system, user_prompt, max_tokens=2048)

        return self._parse_round2_response(text)

    def final_predict(self, question: str, context_text: str, all_debate_results: list[dict]) -> dict:
        """
        Round 3: Final prediction after seeing all Round 2 rebuttals.

        Args:
            question: The prediction question.
            context_text: RAG context.
            all_debate_results: List of all agents' Round 2 results.

        Returns dict with reasoning and final probability.
        """
        template = _load_prompt("debate_round3.txt")

        # Format full Round 2 debate record
        debate_parts = []
        own_round2 = ""
        for result in all_debate_results:
            prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
            entry = (
                f"--- {result['agent_name']} ({result['stance']}) ---\n"
                f"反驳: {result.get('rebuttals', 'N/A')}\n"
                f"修正推理: {result['reasoning']}\n"
                f"修正预测: {prob_str}"
            )
            debate_parts.append(entry)
            if result["agent_name"] == self.name:
                own_round2 = entry

        user_prompt = template.format(
            name=self.name,
            question=question,
            debate_record="\n\n".join(debate_parts),
            own_round2=own_round2,
        )

        system = self._build_system_prompt(context_text)

        text = self._chat(system, user_prompt, max_tokens=1024)

        return self._parse_round3_response(text)

    def meta_predict(self, question: str, own_prediction: float) -> float | None:
        """
        Meta-prediction for Bayesian Truth Serum (BTS).

        Agent predicts what the average prediction across all agents will be.
        This enables peer prediction scoring without ground truth.

        Args:
            question: The prediction question.
            own_prediction: This agent's own final prediction (0-100).

        Returns:
            Predicted average probability (0-100), or None on failure.
        """
        template = _load_prompt("meta_prediction.txt")
        user_prompt = template.format(
            name=self.name,
            question=question,
            own_prediction=own_prediction,
        )

        try:
            text = self._chat(
                f"你是{self.name}，{self.description}",
                user_prompt,
                max_tokens=512,
            )
            # Parse META_PREDICTION: XX%
            match = re.search(r"META_PREDICTION:\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
            if match:
                return float(match.group(1))
            # Fallback
            matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
            if matches:
                return float(matches[-1])
        except Exception as e:
            print(f"  [{self.name}] 元预测失败: {e}")

        return None

    # ── Citation Extraction ─────────────────────────────────────────────────

    def _extract_citations(self, text: str) -> dict:
        """
        Extract RAFT-style citations from agent response.

        Looks for:
          ##begin_quote## ... ##end_quote## [文档 X]

        Returns dict with:
          - quotes: list of {quote, doc_index} dicts
          - cited_doc_indices: set of doc indices cited (1-based)
        """
        pattern = r"##begin_quote##\s*(.*?)\s*##end_quote##\s*\[文档\s*(\d+)\]"
        matches = re.findall(pattern, text, re.DOTALL)

        quotes = []
        cited_doc_indices = set()
        for quote_text, doc_idx_str in matches:
            doc_idx = int(doc_idx_str)
            quotes.append({"quote": quote_text.strip(), "doc_index": doc_idx})
            cited_doc_indices.add(doc_idx)

        return {
            "quotes": quotes,
            "cited_doc_indices": sorted(cited_doc_indices),
        }

    # ── Response Parsing ────────────────────────────────────────────────────

    def _extract_probability(self, text: str) -> float | None:
        """Extract a single probability percentage from text."""
        # Try PREDICTION: XX% or FINAL PREDICTION: XX% or REVISED PREDICTION: XX%
        pattern = r"(?:FINAL |REVISED )?PREDICTION:\s*(\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))

        # Fallback: find any standalone percentage near end of text
        matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
        if matches:
            return float(matches[-1])

        return None

    def _parse_round1_response(self, text: str) -> dict:
        """Parse Round 1 structured prediction response."""
        result = {
            "agent_name": self.name,
            "stance": self.stance,
            "probability": None,
            "reasoning": "",
            "raw_response": text,
            "citations": self._extract_citations(text),
        }

        reasoning_match = re.search(
            r"REASONING:\s*(.+?)(?=\nPREDICTION:|\Z)", text, re.DOTALL
        )
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip()

        result["probability"] = self._extract_probability(text)
        return result

    def _parse_round2_response(self, text: str) -> dict:
        """Parse Round 2 debate response."""
        result = {
            "agent_name": self.name,
            "stance": self.stance,
            "probability": None,
            "rebuttals": "",
            "reasoning": "",
            "raw_response": text,
            "citations": self._extract_citations(text),
        }

        rebuttals_match = re.search(
            r"REBUTTALS:\s*(.+?)(?=\nREVISED REASONING:|\Z)", text, re.DOTALL
        )
        if rebuttals_match:
            result["rebuttals"] = rebuttals_match.group(1).strip()

        reasoning_match = re.search(
            r"REVISED REASONING:\s*(.+?)(?=\nREVISED PREDICTION:|\Z)", text, re.DOTALL
        )
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip()

        result["probability"] = self._extract_probability(text)
        return result

    def _parse_round3_response(self, text: str) -> dict:
        """Parse Round 3 final prediction response."""
        result = {
            "agent_name": self.name,
            "stance": self.stance,
            "probability": None,
            "reasoning": "",
            "raw_response": text,
            "citations": self._extract_citations(text),
        }

        reasoning_match = re.search(
            r"FINAL REASONING:\s*(.+?)(?=\nFINAL PREDICTION:|\Z)", text, re.DOTALL
        )
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip()

        result["probability"] = self._extract_probability(text)
        return result
