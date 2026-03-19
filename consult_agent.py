"""
Consultation agent for the AI Expert Consultation platform.

Each ConsultAgent represents a domain expert who evaluates user opinions,
engages in discussion with other experts, and provides actionable advice.

Level 2 Cloning: Each agent is enhanced with a domain-specific knowledge
profile (analytical frameworks, few-shot examples, typical phrases) that
transforms the base LLM into a specialized expert clone.
"""

import os
import re

from openai import OpenAI

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    PROMPTS_DIR,
)
from knowledge_loader import build_clone_prompt


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class ConsultAgent:
    """A domain expert agent powered by Level 2 AI Clone knowledge profiles."""

    def __init__(
        self,
        name: str,
        role: str,
        stance: str,
        description: str,
        style: str,
        expertise: list[str],
        backend: dict | None = None,
    ):
        self.name = name
        self.role = role
        self.stance = stance
        self.description = description
        self.style = style
        self.expertise = expertise

        if backend:
            self.client = OpenAI(api_key=backend["api_key"], base_url=backend["base_url"])
            self.model = backend["model"]
            self.backend_label = backend["label"]
        else:
            self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
            self.model = DEEPSEEK_MODEL
            self.backend_label = "deepseek"

        self._last_evaluation: dict = {}
        self._conversation_history: list[dict] = []

    def _build_system_prompt(self, context_text: str) -> str:
        """Build system prompt using Level 2 knowledge-enhanced clone profile."""
        return build_clone_prompt(
            expert_name=self.name,
            role=self.role,
            description=self.description,
            style=self.style,
            expertise=self.expertise,
            context_text=context_text,
        )

    def _call_llm(self, system: str, user_prompt: str, max_tokens: int = 2048) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    # ── Phase 1: Evaluate user opinion ───────────────────────────────────

    def evaluate(self, topic: str, user_opinion: str, context_text: str) -> dict:
        """
        Phase 1: Independent evaluation of the user's opinion.

        Returns dict with assessment, agree_points, challenge_points,
        key_insight, confidence, raw_response.
        """
        system = self._build_system_prompt(context_text)
        template = _load_prompt("consult_evaluate.txt")
        user_prompt = template.format(topic=topic, user_opinion=user_opinion)

        raw = self._call_llm(system, user_prompt)
        result = self._parse_evaluation(raw)
        self._last_evaluation = result
        return result

    # ── Phase 2: Interactive conversation with user ──────────────────────

    def respond_to_user(
        self, topic: str, user_opinion: str, user_message: str, context_text: str
    ) -> str:
        """
        Phase 2: Respond to a user's follow-up message in conversation.

        Returns the expert's response text.
        """
        system = self._build_system_prompt(context_text)
        template = _load_prompt("consult_respond.txt")

        # Format conversation history
        history_parts = []
        for msg in self._conversation_history:
            role_label = "用户" if msg["role"] == "user" else self.name
            history_parts.append(f"[{role_label}]: {msg['content']}")
        history_text = "\n\n".join(history_parts) if history_parts else "(无)"

        user_prompt = template.format(
            name=self.name,
            role=self.role,
            topic=topic,
            user_opinion=user_opinion,
            conversation_history=history_text,
            user_message=user_message,
        )

        response_text = self._call_llm(system, user_prompt)

        # Track conversation
        self._conversation_history.append({"role": "user", "content": user_message})
        self._conversation_history.append({"role": "expert", "content": response_text})

        return response_text

    # ── Phase 3: Expert discussion ───────────────────────────────────────

    def discuss(
        self, topic: str, user_opinion: str, other_evaluations: list[dict], context_text: str
    ) -> dict:
        """
        Phase 3: Discuss with other experts about the user's opinion.

        Returns dict with responses, updated_assessment, blind_spots, confidence.
        """
        system = self._build_system_prompt(context_text)
        template = _load_prompt("consult_discuss.txt")

        # Format other experts' evaluations
        other_parts = []
        response_template_parts = []
        for ev in other_evaluations:
            other_parts.append(
                f"--- {ev['agent_name']}（{ev.get('role', '')}）---\n"
                f"评价: {ev['assessment']}\n"
                f"认同: {ev.get('agree_points', '')}\n"
                f"质疑: {ev.get('challenge_points', '')}\n"
                f"关键洞察: {ev.get('key_insight', '')}\n"
                f"置信度: {ev.get('confidence', 'N/A')}%"
            )
            response_template_parts.append(
                f"Re: {ev['agent_name']}: <你的回应>"
            )

        # Own evaluation
        own_eval = (
            f"评价: {self._last_evaluation.get('assessment', '')}\n"
            f"认同: {self._last_evaluation.get('agree_points', '')}\n"
            f"质疑: {self._last_evaluation.get('challenge_points', '')}\n"
            f"置信度: {self._last_evaluation.get('confidence', 'N/A')}%"
        )

        user_prompt = template.format(
            name=self.name,
            topic=topic,
            user_opinion=user_opinion,
            other_evaluations="\n\n".join(other_parts),
            own_evaluation=own_eval,
            response_template="\n".join(response_template_parts),
        )

        raw = self._call_llm(system, user_prompt)
        return self._parse_discussion(raw)

    # ── Phase 4: Final assessment ────────────────────────────────────────

    def final_assess(
        self, topic: str, user_opinion: str, all_discussions: list[dict], context_text: str
    ) -> dict:
        """
        Phase 4: Final assessment after full expert discussion.

        Returns dict with final_assessment, recommendation, risk_warning, confidence.
        """
        system = self._build_system_prompt(context_text)
        template = _load_prompt("consult_final.txt")

        # Format discussion record
        disc_parts = []
        own_disc = ""
        for d in all_discussions:
            entry = (
                f"--- {d['agent_name']}（{d.get('role', '')}）---\n"
                f"回应: {d.get('responses', '')}\n"
                f"更新评价: {d.get('updated_assessment', '')}\n"
                f"盲点: {d.get('blind_spots', '')}\n"
                f"置信度: {d.get('confidence', 'N/A')}%"
            )
            disc_parts.append(entry)
            if d["agent_name"] == self.name:
                own_disc = entry

        user_prompt = template.format(
            name=self.name,
            topic=topic,
            user_opinion=user_opinion,
            discussion_record="\n\n".join(disc_parts),
            own_discussion=own_disc,
        )

        raw = self._call_llm(system, user_prompt, max_tokens=1024)
        return self._parse_final(raw)

    # ── Parsing helpers ──────────────────────────────────────────────────

    def _extract_section(self, text: str, section: str, next_sections: list[str]) -> str:
        """Extract content between a section header and the next section."""
        next_pattern = "|".join(re.escape(s) for s in next_sections) if next_sections else r"\Z"
        pattern = rf"{re.escape(section)}:\s*(.+?)(?=\n(?:{next_pattern}):|\Z)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_confidence(self, text: str) -> float | None:
        match = re.search(r"CONFIDENCE:\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
        return float(matches[-1]) if matches else None

    def _parse_evaluation(self, text: str) -> dict:
        return {
            "agent_name": self.name,
            "role": self.role,
            "stance": self.stance,
            "assessment": self._extract_section(text, "ASSESSMENT", ["AGREE_POINTS", "CHALLENGE_POINTS", "KEY_INSIGHT", "CONFIDENCE"]),
            "agree_points": self._extract_section(text, "AGREE_POINTS", ["CHALLENGE_POINTS", "KEY_INSIGHT", "CONFIDENCE"]),
            "challenge_points": self._extract_section(text, "CHALLENGE_POINTS", ["KEY_INSIGHT", "CONFIDENCE"]),
            "key_insight": self._extract_section(text, "KEY_INSIGHT", ["CONFIDENCE"]),
            "confidence": self._extract_confidence(text),
            "raw_response": text,
        }

    def _parse_discussion(self, text: str) -> dict:
        return {
            "agent_name": self.name,
            "role": self.role,
            "stance": self.stance,
            "responses": self._extract_section(text, "RESPONSES", ["UPDATED_ASSESSMENT", "BLIND_SPOTS", "CONFIDENCE"]),
            "updated_assessment": self._extract_section(text, "UPDATED_ASSESSMENT", ["BLIND_SPOTS", "CONFIDENCE"]),
            "blind_spots": self._extract_section(text, "BLIND_SPOTS", ["CONFIDENCE"]),
            "confidence": self._extract_confidence(text),
            "raw_response": text,
        }

    def _parse_final(self, text: str) -> dict:
        return {
            "agent_name": self.name,
            "role": self.role,
            "stance": self.stance,
            "final_assessment": self._extract_section(text, "FINAL_ASSESSMENT", ["RECOMMENDATION", "RISK_WARNING", "CONFIDENCE"]),
            "recommendation": self._extract_section(text, "RECOMMENDATION", ["RISK_WARNING", "CONFIDENCE"]),
            "risk_warning": self._extract_section(text, "RISK_WARNING", ["CONFIDENCE"]),
            "confidence": self._extract_confidence(text),
            "raw_response": text,
        }
