"""
Debate pipeline orchestrator.

Coordinates RAG retrieval and 3-round debate between agents for prediction market questions.

Usage:
    python debate.py
"""

import json
import os
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from agent import DebateAgent
from aggregator import (
    ReputationTracker,
    aggregate_simple_average,
    aggregate_median,
    aggregate_trimmed_mean,
    aggregate_logit_average,
    aggregate_extremized,
    aggregate_reputation_weighted,
    aggregate_lmsr,
    aggregate_peer_prediction,
    aggregate_hybrid,
)
from config import (
    AGENT_PERSONAS,
    RESULTS_DIR,
    REPUTATION_DECAY,
    LMSR_LIQUIDITY,
    HYBRID_LAMBDA_MARKET,
    HYBRID_LAMBDA_REPUTATION,
    HYBRID_LAMBDA_BTS,
    EXTREMIZATION_D,
    get_available_backends,
)
from info_partition import partition_documents, format_agent_context
from retriever import NewsRetriever


class DebatePipeline:
    """Orchestrates the full 3-round debate pipeline."""

    def __init__(
        self,
        reputation_tracker: ReputationTracker | None = None,
        use_multi_model: bool = True,
        use_info_partition: bool = True,
    ):
        self.retriever = NewsRetriever()
        self.use_info_partition = use_info_partition

        # Assign different LLM backends to agents (round-robin)
        backends = get_available_backends() if use_multi_model else []

        self.agents = []
        for i, persona in enumerate(AGENT_PERSONAS):
            backend = backends[i % len(backends)] if backends else None
            self.agents.append(DebateAgent(**persona, backend=backend))

        agent_names = [a.name for a in self.agents]
        self.reputation_tracker = reputation_tracker or ReputationTracker(
            agent_names, decay=REPUTATION_DECAY
        )

        # Log backend assignment
        if backends and len(backends) > 1:
            assignment = {a.name: a.backend_label for a in self.agents}
            labels = set(assignment.values())
            print(f"[Multi-Model] {len(labels)} backends: {labels}")
            for name, label in assignment.items():
                print(f"  {name} → {label}")

    def run(self, question: str, market_price: float | None = None) -> dict:
        """
        Run a complete 3-round debate for a prediction question.

        Args:
            question: The prediction market question.
            market_price: Optional current market probability (0-1 scale).

        Returns:
            Full result dict with RAG sources, all rounds, and aggregated probability.
        """
        print(f"\n{'='*60}")
        print(f"问题: {question}")
        if market_price is not None:
            print(f"市场价格: {market_price*100:.1f}%")
        print(f"{'='*60}")

        # 1. RAG retrieval (RAFT: mixed relevant + distractor docs)
        print("\n[RAG] 正在检索相关信息...")
        rag_result = self.retriever.retrieve(question)
        context_text = rag_result["context_text"]
        mixed_docs = rag_result.get("mixed_docs", [])
        oracle_indices = set(rag_result.get("oracle_indices", []))
        num_relevant = len(rag_result["relevant"])
        num_distractors = len(rag_result["distractors"])
        print(f"[RAG] 找到 {num_relevant} 条相关来源, {num_distractors} 条干扰文档 (RAFT 混合)")

        # 1b. Information partitioning (if enabled)
        agent_contexts = {}
        if self.use_info_partition and mixed_docs:
            agent_names = [a.name for a in self.agents]
            partitioned = partition_documents(mixed_docs, agent_names)
            stats = partitioned.get("_stats", {})
            print(f"[InfoPartition] Shared: {stats.get('shared_count', 0)}, "
                  f"Private pool: {stats.get('private_pool_size', 0)}")
            for agent in self.agents:
                agent_docs = partitioned.get(agent.name, mixed_docs)
                agent_contexts[agent.name] = format_agent_context(agent_docs)
        else:
            # All agents see same context (original behavior)
            for agent in self.agents:
                agent_contexts[agent.name] = context_text

        # 2. Round 1: Independent predictions (parallel)
        print(f"\n{'#'*60}")
        print("Round 1: 独立预测 (并行)")
        print(f"{'#'*60}")

        def _run_round1(agent):
            try:
                ctx = agent_contexts[agent.name]
                result = agent.predict(question, ctx)
                prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
                print(f"  [{agent.name}] 预测: {prob_str}")
                return result
            except Exception as e:
                print(f"  [{agent.name}] 错误: {e}")
                return {
                    "agent_name": agent.name,
                    "stance": agent.stance,
                    "probability": None,
                    "reasoning": f"(预测失败: {e})",
                    "raw_response": "",
                }

        round1_by_agent = {}
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_run_round1, a): a for a in self.agents}
            for future in as_completed(futures):
                agent = futures[future]
                round1_by_agent[agent.name] = future.result()
        round1 = [round1_by_agent[a.name] for a in self.agents]

        # 3. Round 2: Cross-rebuttal (parallel)
        print(f"\n{'#'*60}")
        print("Round 2: 交叉反驳 (并行)")
        print(f"{'#'*60}")

        def _run_round2(i, agent):
            others = [r for j, r in enumerate(round1) if j != i]
            try:
                result = agent.debate(question, agent_contexts[agent.name], others)
                prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
                print(f"  [{agent.name}] 修正预测: {prob_str}")
                return result
            except Exception as e:
                print(f"  [{agent.name}] 错误: {e}")
                fallback = round1[i].copy()
                fallback["rebuttals"] = f"(辩论失败: {e})"
                return fallback

        round2_by_agent = {}
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_run_round2, i, a): a for i, a in enumerate(self.agents)}
            for future in as_completed(futures):
                agent = futures[future]
                round2_by_agent[agent.name] = future.result()
        round2 = [round2_by_agent[a.name] for a in self.agents]

        # 4. Round 3: Final predictions (parallel)
        print(f"\n{'#'*60}")
        print("Round 3: 最终预测 (并行)")
        print(f"{'#'*60}")

        def _run_round3(agent):
            try:
                result = agent.final_predict(question, agent_contexts[agent.name], round2)
                prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
                print(f"  [{agent.name}] 最终预测: {prob_str}")
                return result
            except Exception as e:
                print(f"  [{agent.name}] 错误: {e}")
                for r2 in round2:
                    if r2["agent_name"] == agent.name:
                        return r2.copy()
                return {"agent_name": agent.name, "stance": agent.stance,
                        "probability": None, "reasoning": f"(失败: {e})", "raw_response": ""}

        round3_by_agent = {}
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_run_round3, a): a for a in self.agents}
            for future in as_completed(futures):
                agent = futures[future]
                round3_by_agent[agent.name] = future.result()
        round3 = [round3_by_agent[a.name] for a in self.agents]

        # 5. Meta-predictions for BTS (parallel)
        print(f"\n{'#'*60}")
        print("Meta-Prediction: 元预测 (并行)")
        print(f"{'#'*60}")

        meta_predictions = {}

        def _run_meta(agent, own_pred):
            try:
                meta = agent.meta_predict(question, own_pred)
                if meta is not None:
                    print(f"  [{agent.name}] 元预测 (预测平均值): {meta}%")
                return meta
            except Exception as e:
                print(f"  [{agent.name}] 元预测失败: {e}")
                return None

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {}
            for agent, r3 in zip(self.agents, round3):
                own_pred = r3.get("probability")
                if own_pred is not None:
                    futures[pool.submit(_run_meta, agent, own_pred)] = agent
            for future in as_completed(futures):
                agent = futures[future]
                result_meta = future.result()
                if result_meta is not None:
                    meta_predictions[agent.name] = result_meta

        # 6. Aggregate with all mechanisms
        reputation_weights = self.reputation_tracker.get_weights()

        agg_results = {
            "simple_average": aggregate_simple_average(round3),
            "median": aggregate_median(round3),
            "trimmed_mean": aggregate_trimmed_mean(round3),
            "logit_average": aggregate_logit_average(round3),
            "extremized": aggregate_extremized(round3, d=EXTREMIZATION_D),
            "reputation_weighted": aggregate_reputation_weighted(round3, reputation_weights),
            "lmsr_market": aggregate_lmsr(
                round3,
                budgets={name: 100.0 * (1 + w) for name, w in reputation_weights.items()},
                liquidity=LMSR_LIQUIDITY,
            ),
            "peer_prediction": aggregate_peer_prediction(round3, meta_predictions or None),
            "hybrid": aggregate_hybrid(
                round3,
                reputation_weights=reputation_weights,
                meta_predictions=meta_predictions or None,
                lmsr_liquidity=LMSR_LIQUIDITY,
                lambda_market=HYBRID_LAMBDA_MARKET,
                lambda_reputation=HYBRID_LAMBDA_REPUTATION,
                lambda_bts=HYBRID_LAMBDA_BTS,
            ),
        }

        # Backwards-compatible values
        avg_prob = agg_results["simple_average"]["probability"]

        # Round 1 average for no-debate comparison
        r1_valid = [r["probability"] for r in round1 if r["probability"] is not None]
        r1_avg = statistics.mean(r1_valid) if r1_valid else None

        # 6. RAFT metrics: citation accuracy & distractor rejection
        raft_metrics = self._compute_raft_metrics(
            round1 + round2 + round3, oracle_indices, mixed_docs
        )

        result = {
            "question": question,
            "market_price": market_price,
            "timestamp": datetime.utcnow().isoformat(),
            "rag_sources": rag_result["relevant"],
            "mixed_docs_count": len(mixed_docs),
            "oracle_count": len(oracle_indices),
            "distractor_count": num_distractors,
            "raft_metrics": raft_metrics,
            "rounds": {
                "round1": round1,
                "round2": round2,
                "round3": round3,
            },
            "meta_predictions": meta_predictions,
            "round1_average": round(r1_avg, 1) if r1_avg is not None else None,
            "aggregated_probability": round(avg_prob, 1) if avg_prob is not None else None,
            "aggregation_mechanisms": {
                method: {
                    "probability": res["probability"],
                    "details": res.get("details", {}),
                }
                for method, res in agg_results.items()
            },
            "reputation_snapshot": self.reputation_tracker.snapshot(),
            "agents": [
                {"name": a.name, "stance": a.stance, "final": r}
                for a, r in zip(self.agents, round3)
            ],
        }

        # Print summary
        print(f"\n{'='*60}")
        print("辩论结果汇总")
        print(f"{'='*60}")
        print(f"  Round 1 平均 (无辩论): {result['round1_average']}%")
        print(f"\n  [聚合机制对比]")
        for method, res in agg_results.items():
            prob = res["probability"]
            prob_str = f"{prob:.1f}%" if prob is not None else "N/A"
            print(f"  {method:25s}: {prob_str}")
        if market_price is not None:
            print(f"  {'market_price':25s}: {market_price*100:.1f}%")
        print(f"\n  [RAFT 指标]")
        print(f"  引用准确率: {raft_metrics['citation_accuracy']:.1%}")
        print(f"  干扰拒绝率: {raft_metrics['distractor_rejection_rate']:.1%}")
        print(f"  总引用数:   {raft_metrics['total_citations']}")

        return result


    def _compute_raft_metrics(
        self, all_round_results: list[dict], oracle_indices: set, mixed_docs: list
    ) -> dict:
        """
        Compute RAFT evaluation metrics from citation data across all rounds.

        Args:
            all_round_results: Combined results from rounds 1-3.
            oracle_indices: Set of 0-based indices that are oracle docs in mixed_docs.
            mixed_docs: The shuffled mixed document list.

        Returns:
            Dict with citation_accuracy, distractor_rejection_rate, total_citations.
        """
        # Collect all cited doc indices (1-based from agent output → convert to 0-based)
        all_cited_0based = set()
        total_citations = 0

        for result in all_round_results:
            citations = result.get("citations", {})
            if isinstance(citations, dict):
                for doc_idx_1based in citations.get("cited_doc_indices", set()):
                    all_cited_0based.add(doc_idx_1based - 1)  # convert to 0-based
                total_citations += len(citations.get("quotes", []))

        # Citation accuracy: of all cited docs, what fraction are oracle?
        if all_cited_0based:
            oracle_cited = all_cited_0based & oracle_indices
            citation_accuracy = len(oracle_cited) / len(all_cited_0based)
        else:
            citation_accuracy = 0.0

        # Distractor rejection rate: of all distractor docs, what fraction were NOT cited?
        num_docs = len(mixed_docs)
        distractor_indices = set(range(num_docs)) - oracle_indices
        if distractor_indices:
            distractors_not_cited = distractor_indices - all_cited_0based
            distractor_rejection_rate = len(distractors_not_cited) / len(distractor_indices)
        else:
            distractor_rejection_rate = 1.0

        return {
            "citation_accuracy": citation_accuracy,
            "distractor_rejection_rate": distractor_rejection_rate,
            "total_citations": total_citations,
            "unique_docs_cited": len(all_cited_0based),
            "oracle_docs_cited": len(all_cited_0based & oracle_indices) if oracle_indices else 0,
            "distractor_docs_cited": len(all_cited_0based - oracle_indices),
        }


def main():
    """Run a single question for testing."""
    pipeline = DebatePipeline()

    # Test question
    question = "2025 NBA 总决赛冠军是否为波士顿凯尔特人？"
    market_price = 0.28

    result = pipeline.run(question, market_price)

    # Save result
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(RESULTS_DIR, "test_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 {output_path}")


if __name__ == "__main__":
    main()
