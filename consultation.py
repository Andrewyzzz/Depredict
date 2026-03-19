"""
Consultation pipeline orchestrator.

Coordinates the multi-phase expert consultation process:
  Phase 1: Independent expert evaluations
  Phase 2: User-expert interactive conversation (handled by Streamlit UI)
  Phase 3: Expert-to-expert discussion
  Phase 4: Final assessments and report synthesis
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from config import RESULTS_DIR, get_available_backends
from consult_agent import ConsultAgent
from expert_panels import get_panel
from retriever import NewsRetriever


class ConsultationPipeline:
    """Orchestrates the full expert consultation pipeline."""

    def __init__(self, domain: str, use_multi_model: bool = True):
        self.domain = domain
        self.retriever = NewsRetriever()

        # Build expert agents from domain panel
        panel = get_panel(domain)
        backends = get_available_backends() if use_multi_model else []

        self.agents: list[ConsultAgent] = []
        for i, expert in enumerate(panel):
            backend = backends[i % len(backends)] if backends else None
            self.agents.append(ConsultAgent(**expert, backend=backend))

        if backends and len(backends) > 1:
            labels = {a.name: a.backend_label for a in self.agents}
            print(f"[Multi-Model] Backends: {set(labels.values())}")

    def retrieve_context(self, topic: str) -> dict:
        """Retrieve background information for the topic."""
        print(f"\n[RAG] Retrieving context for: {topic}")
        rag_result = self.retriever.retrieve(topic)
        print(f"[RAG] Found {len(rag_result['relevant'])} sources")
        return rag_result

    def phase1_evaluate(
        self, topic: str, user_opinion: str, context_text: str
    ) -> list[dict]:
        """
        Phase 1: Each expert independently evaluates the user's opinion.

        Returns list of evaluation dicts.
        """
        print(f"\n{'#'*60}")
        print("Phase 1: Expert Evaluations")
        print(f"{'#'*60}")

        def _run(agent):
            try:
                result = agent.evaluate(topic, user_opinion, context_text)
                conf = result.get("confidence", "N/A")
                print(f"  [{agent.name}] Assessment done (confidence: {conf}%)")
                return result
            except Exception as e:
                print(f"  [{agent.name}] Error: {e}")
                return {
                    "agent_name": agent.name,
                    "role": agent.role,
                    "stance": agent.stance,
                    "assessment": f"(evaluation failed: {e})",
                    "agree_points": "",
                    "challenge_points": "",
                    "key_insight": "",
                    "confidence": None,
                    "raw_response": "",
                }

        results_by_name = {}
        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_run, a): a for a in self.agents}
            for future in as_completed(futures):
                agent = futures[future]
                results_by_name[agent.name] = future.result()

        return [results_by_name[a.name] for a in self.agents]

    def phase3_discuss(
        self, topic: str, user_opinion: str, evaluations: list[dict], context_text: str
    ) -> list[dict]:
        """
        Phase 3: Experts discuss each other's evaluations.

        Returns list of discussion dicts.
        """
        print(f"\n{'#'*60}")
        print("Phase 3: Expert Discussion")
        print(f"{'#'*60}")

        def _run(i, agent):
            others = [ev for j, ev in enumerate(evaluations) if j != i]
            try:
                result = agent.discuss(topic, user_opinion, others, context_text)
                conf = result.get("confidence", "N/A")
                print(f"  [{agent.name}] Discussion done (confidence: {conf}%)")
                return result
            except Exception as e:
                print(f"  [{agent.name}] Error: {e}")
                return {
                    "agent_name": agent.name,
                    "role": agent.role,
                    "stance": agent.stance,
                    "responses": f"(discussion failed: {e})",
                    "updated_assessment": "",
                    "blind_spots": "",
                    "confidence": None,
                    "raw_response": "",
                }

        results_by_name = {}
        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_run, i, a): a for i, a in enumerate(self.agents)}
            for future in as_completed(futures):
                agent = futures[future]
                results_by_name[agent.name] = future.result()

        return [results_by_name[a.name] for a in self.agents]

    def phase4_final(
        self, topic: str, user_opinion: str, discussions: list[dict], context_text: str
    ) -> list[dict]:
        """
        Phase 4: Each expert gives final assessment.

        Returns list of final assessment dicts.
        """
        print(f"\n{'#'*60}")
        print("Phase 4: Final Assessments")
        print(f"{'#'*60}")

        def _run(agent):
            try:
                result = agent.final_assess(topic, user_opinion, discussions, context_text)
                conf = result.get("confidence", "N/A")
                print(f"  [{agent.name}] Final assessment done (confidence: {conf}%)")
                return result
            except Exception as e:
                print(f"  [{agent.name}] Error: {e}")
                return {
                    "agent_name": agent.name,
                    "role": agent.role,
                    "stance": agent.stance,
                    "final_assessment": f"(failed: {e})",
                    "recommendation": "",
                    "risk_warning": "",
                    "confidence": None,
                    "raw_response": "",
                }

        results_by_name = {}
        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_run, a): a for a in self.agents}
            for future in as_completed(futures):
                agent = futures[future]
                results_by_name[agent.name] = future.result()

        return [results_by_name[a.name] for a in self.agents]

    def run_full(self, topic: str, user_opinion: str) -> dict:
        """
        Run Phases 1, 3, 4 (Phase 2 is interactive, handled by UI).

        Returns full consultation result.
        """
        print(f"\n{'='*60}")
        print(f"Topic: {topic}")
        print(f"User Opinion: {user_opinion[:100]}...")
        print(f"Domain: {self.domain}")
        print(f"{'='*60}")

        # Retrieve context
        rag_result = self.retrieve_context(topic)
        context_text = rag_result["context_text"]

        # Phase 1
        evaluations = self.phase1_evaluate(topic, user_opinion, context_text)

        # Phase 3
        discussions = self.phase3_discuss(topic, user_opinion, evaluations, context_text)

        # Phase 4
        finals = self.phase4_final(topic, user_opinion, discussions, context_text)

        # Synthesize report
        report = self._synthesize_report(topic, user_opinion, evaluations, discussions, finals)

        result = {
            "topic": topic,
            "user_opinion": user_opinion,
            "domain": self.domain,
            "timestamp": datetime.utcnow().isoformat(),
            "rag_sources": rag_result["relevant"],
            "phases": {
                "evaluations": evaluations,
                "discussions": discussions,
                "finals": finals,
            },
            "report": report,
            "experts": [
                {"name": a.name, "role": a.role, "stance": a.stance}
                for a in self.agents
            ],
        }

        # Print report
        print(f"\n{'='*60}")
        print("CONSULTATION REPORT")
        print(f"{'='*60}")
        print(report["summary"])

        return result

    def _synthesize_report(
        self,
        topic: str,
        user_opinion: str,
        evaluations: list[dict],
        discussions: list[dict],
        finals: list[dict],
    ) -> dict:
        """Synthesize a structured consultation report from all phases."""

        # Collect consensus and disagreements
        assessments = [ev.get("assessment", "") for ev in evaluations]
        challenges = [ev.get("challenge_points", "") for ev in evaluations if ev.get("challenge_points")]
        insights = [ev.get("key_insight", "") for ev in evaluations if ev.get("key_insight")]
        blind_spots = [d.get("blind_spots", "") for d in discussions if d.get("blind_spots")]
        recommendations = [f.get("recommendation", "") for f in finals if f.get("recommendation")]
        risk_warnings = [f.get("risk_warning", "") for f in finals if f.get("risk_warning")]

        # Confidence tracking
        eval_confidences = [ev.get("confidence") for ev in evaluations if ev.get("confidence") is not None]
        final_confidences = [f.get("confidence") for f in finals if f.get("confidence") is not None]
        avg_eval_conf = sum(eval_confidences) / len(eval_confidences) if eval_confidences else None
        avg_final_conf = sum(final_confidences) / len(final_confidences) if final_confidences else None

        # Build summary
        summary_parts = [
            f"## Consultation Report: {topic}\n",
            f"### Your Opinion\n{user_opinion}\n",
            f"### Expert Panel ({len(evaluations)} experts)\n",
        ]

        for ev in evaluations:
            summary_parts.append(f"- **{ev['agent_name']}** ({ev.get('role', '')}): {ev.get('assessment', 'N/A')}")
        summary_parts.append("")

        if insights:
            summary_parts.append("### Key Insights")
            for i, insight in enumerate(insights):
                summary_parts.append(f"{i+1}. {insight}")
            summary_parts.append("")

        if blind_spots:
            summary_parts.append("### Blind Spots Identified")
            for bs in blind_spots:
                if bs:
                    summary_parts.append(f"- {bs}")
            summary_parts.append("")

        if recommendations:
            summary_parts.append("### Recommendations")
            for rec in recommendations:
                if rec:
                    summary_parts.append(f"- {rec}")
            summary_parts.append("")

        if risk_warnings:
            summary_parts.append("### Risk Warnings")
            for rw in risk_warnings:
                if rw:
                    summary_parts.append(f"- {rw}")
            summary_parts.append("")

        if avg_eval_conf is not None and avg_final_conf is not None:
            summary_parts.append(f"### Confidence Shift")
            summary_parts.append(f"- Phase 1 avg confidence: {avg_eval_conf:.1f}%")
            summary_parts.append(f"- Phase 4 avg confidence: {avg_final_conf:.1f}%")

        return {
            "summary": "\n".join(summary_parts),
            "assessments": assessments,
            "challenges": challenges,
            "insights": insights,
            "blind_spots": blind_spots,
            "recommendations": recommendations,
            "risk_warnings": risk_warnings,
            "avg_eval_confidence": avg_eval_conf,
            "avg_final_confidence": avg_final_conf,
        }


def save_consultation(result: dict, filename: str | None = None) -> str:
    """Save consultation result to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if filename is None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"consult_{result['domain']}_{ts}.json"
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nResult saved to {path}")
    return path
