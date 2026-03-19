"""
Debate pipeline orchestrator (refactored with progress callbacks).

Coordinates RAG retrieval and 3-round debate between agents for prediction market questions.
Core logic is identical to the original debate.py; the key additions are:
  - progress_callback for real-time stage/percent updates
  - checkpoint_manager for resuming interrupted debates
"""

import json
import os
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable

from ..core.debate_agent import DebateAgent
from ..core.aggregator import (
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
from ..config import Config
from ..core.info_partition import partition_documents, format_agent_context
from ..core.retriever import NewsRetriever


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
        backends = Config.get_available_backends() if use_multi_model else []

        self.agents = []
        for i, persona in enumerate(Config.AGENT_PERSONAS):
            backend = backends[i % len(backends)] if backends else None
            self.agents.append(DebateAgent(**persona, backend=backend))

        agent_names = [a.name for a in self.agents]
        self.reputation_tracker = reputation_tracker or ReputationTracker(
            agent_names, decay=Config.REPUTATION_DECAY
        )

        # Log backend assignment
        if backends and len(backends) > 1:
            assignment = {a.name: a.backend_label for a in self.agents}
            labels = set(assignment.values())
            print(f"[Multi-Model] {len(labels)} backends: {labels}")
            for name, label in assignment.items():
                print(f"  {name} → {label}")

    def run(
        self,
        question: str,
        market_price: float | None = None,
        progress_callback: Callable | None = None,
        checkpoint_manager=None,
    ) -> dict:
        """
        Run a complete 3-round debate for a prediction question.

        Args:
            question: The prediction market question.
            market_price: Optional current market probability (0-1 scale).
            progress_callback: Optional callback(stage, percent, message, **kwargs).
            checkpoint_manager: Optional checkpoint manager for resume support.

        Returns:
            Full result dict with RAG sources, all rounds, and aggregated probability.
        """

        def _cb(stage: str, percent: int, message: str, **kwargs):
            if progress_callback is not None:
                progress_callback(stage=stage, percent=percent, message=message, **kwargs)

        # Check for existing checkpoint to resume from
        checkpoint_data = {}
        if checkpoint_manager is not None:
            checkpoint_data = checkpoint_manager.load(question) or {}

        print(f"\n{'='*60}")
        print(f"问题: {question}")
        if market_price is not None:
            print(f"市场价格: {market_price*100:.1f}%")
        print(f"{'='*60}")

        # 1. RAG retrieval
        if "rag_result" in checkpoint_data:
            print("\n[RAG] Resuming from checkpoint...")
            rag_result = checkpoint_data["rag_result"]
            _cb("retrieving", 100, "RAG retrieval restored from checkpoint")
        else:
            print("\n[RAG] 正在检索相关信息...")
            _cb("retrieving", 0, "Starting RAG retrieval...")
            rag_result = self.retriever.retrieve(question)
            _cb("retrieving", 100, "RAG retrieval complete")

            if checkpoint_manager is not None:
                checkpoint_data["rag_result"] = rag_result
                checkpoint_manager.save(question, checkpoint_data)

        context_text = rag_result["context_text"]
        documents = rag_result.get("documents", [])
        print(f"[RAG] 找到 {len(documents)} 条相关来源")

        # 1b. Entity extraction (knowledge graph)
        entity_graph = None
        _cb("extracting_entities", 0, "Entity extraction starting...")
        try:
            from ..services.entity_extractor import extract_entities_from_docs
            backends = Config.get_available_backends()
            entity_graph = extract_entities_from_docs(
                documents, question,
                backend=backends[0] if backends else None,
            )
            graph_data = entity_graph.to_dict()
            print(f"[EntityGraph] {len(graph_data['entities'])} entities, "
                  f"{len(graph_data['relations'])} relations, "
                  f"{len(graph_data['timeline'])} timeline events")
            _cb("extracting_entities", 100, f"Extracted {len(graph_data['entities'])} entities")
        except Exception as e:
            print(f"[EntityGraph] Extraction failed: {e}")
            _cb("extracting_entities", 100, "Entity extraction skipped")

        # 1c. Information partitioning (if enabled)
        # Build knowledge graph context suffix (shared across all agents)
        kg_context = ""
        if entity_graph is not None:
            kg_text = entity_graph.format_for_context()
            if kg_text:
                kg_context = f"\n\n---\n\n[知识图谱摘要]\n{kg_text}"

        agent_contexts = {}
        if self.use_info_partition and documents:
            agent_names = [a.name for a in self.agents]
            partitioned = partition_documents(documents, agent_names)
            stats = partitioned.get("_stats", {})
            print(f"[InfoPartition] Shared: {stats.get('shared_count', 0)}, "
                  f"Private pool: {stats.get('private_pool_size', 0)}")
            for agent in self.agents:
                agent_docs = partitioned.get(agent.name, documents)
                agent_contexts[agent.name] = format_agent_context(agent_docs) + kg_context
        else:
            # All agents see same context (original behavior)
            for agent in self.agents:
                agent_contexts[agent.name] = context_text + kg_context

        # 2. Round 1: Independent predictions (parallel)
        if "round1" in checkpoint_data:
            print("\n[Round 1] Resuming from checkpoint...")
            round1 = checkpoint_data["round1"]
            _cb("debating_r1", 100, "Round 1 restored from checkpoint")
        else:
            print(f"\n{'#'*60}")
            print("Round 1: 独立预测 (并行)")
            print(f"{'#'*60}")
            _cb("debating_r1", 0, "Round 1 starting...")

            completed_count = 0
            total_agents = len(self.agents)

            def _run_round1(agent):
                nonlocal completed_count
                try:
                    ctx = agent_contexts[agent.name]
                    result = agent.predict(question, ctx)
                    prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
                    print(f"  [{agent.name}] 预测: {prob_str}")
                    completed_count += 1
                    _cb(
                        "debating_r1",
                        int(completed_count / total_agents * 100),
                        f"Round 1: {agent.name} complete ({completed_count}/{total_agents})",
                        current=completed_count,
                        total=total_agents,
                        agent_name=agent.name,
                        data=result,
                    )
                    return result
                except Exception as e:
                    print(f"  [{agent.name}] 错误: {e}")
                    completed_count += 1
                    result = {
                        "agent_name": agent.name,
                        "stance": agent.stance,
                        "probability": None,
                        "reasoning": f"(预测失败: {e})",
                        "raw_response": "",
                    }
                    _cb(
                        "debating_r1",
                        int(completed_count / total_agents * 100),
                        f"Round 1: {agent.name} failed ({completed_count}/{total_agents})",
                        current=completed_count,
                        total=total_agents,
                        agent_name=agent.name,
                        data=result,
                    )
                    return result

            round1_by_agent = {}
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(_run_round1, a): a for a in self.agents}
                for future in as_completed(futures, timeout=300):
                    agent = futures[future]
                    try:
                        round1_by_agent[agent.name] = future.result(timeout=120)
                    except Exception as e:
                        print(f"  [{agent.name}] Round 1 timed out: {e}")
                        round1_by_agent[agent.name] = {
                            "agent_name": agent.name, "stance": agent.stance,
                            "probability": None, "reasoning": f"(超时: {e})", "raw_response": "",
                        }
            round1 = [round1_by_agent.get(a.name, {
                "agent_name": a.name, "stance": a.stance,
                "probability": None, "reasoning": "(未完成)", "raw_response": "",
            }) for a in self.agents]

            if checkpoint_manager is not None:
                checkpoint_data["round1"] = round1
                checkpoint_manager.save(question, checkpoint_data)

        # 3. Round 2: Cross-rebuttal (parallel)
        if "round2" in checkpoint_data:
            print("\n[Round 2] Resuming from checkpoint...")
            round2 = checkpoint_data["round2"]
            _cb("debating_r2", 100, "Round 2 restored from checkpoint")
        else:
            print(f"\n{'#'*60}")
            print("Round 2: 交叉反驳 (并行)")
            print(f"{'#'*60}")
            _cb("debating_r2", 0, "Round 2 starting...")

            completed_count_r2 = 0
            total_agents = len(self.agents)

            def _run_round2(i, agent):
                nonlocal completed_count_r2
                others = [r for j, r in enumerate(round1) if j != i]
                try:
                    result = agent.debate(question, agent_contexts[agent.name], others)
                    prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
                    print(f"  [{agent.name}] 修正预测: {prob_str}")
                    completed_count_r2 += 1
                    _cb(
                        "debating_r2",
                        int(completed_count_r2 / total_agents * 100),
                        f"Round 2: {agent.name} complete ({completed_count_r2}/{total_agents})",
                        current=completed_count_r2,
                        total=total_agents,
                        agent_name=agent.name,
                        data=result,
                    )
                    return result
                except Exception as e:
                    print(f"  [{agent.name}] 错误: {e}")
                    completed_count_r2 += 1
                    fallback = round1[i].copy()
                    fallback["rebuttals"] = f"(辩论失败: {e})"
                    _cb(
                        "debating_r2",
                        int(completed_count_r2 / total_agents * 100),
                        f"Round 2: {agent.name} failed ({completed_count_r2}/{total_agents})",
                        current=completed_count_r2,
                        total=total_agents,
                        agent_name=agent.name,
                        data=fallback,
                    )
                    return fallback

            round2_by_agent = {}
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(_run_round2, i, a): a for i, a in enumerate(self.agents)}
                for future in as_completed(futures, timeout=300):
                    agent = futures[future]
                    try:
                        round2_by_agent[agent.name] = future.result(timeout=120)
                    except Exception as e:
                        print(f"  [{agent.name}] Round 2 timed out: {e}")
                        round2_by_agent[agent.name] = {
                            "agent_name": agent.name, "stance": agent.stance,
                            "probability": None, "reasoning": f"(超时: {e})", "raw_response": "",
                        }
            round2 = [round2_by_agent.get(a.name, {
                "agent_name": a.name, "stance": a.stance,
                "probability": None, "reasoning": "(未完成)", "raw_response": "",
            }) for a in self.agents]

            if checkpoint_manager is not None:
                checkpoint_data["round2"] = round2
                checkpoint_manager.save(question, checkpoint_data)

        # 4. Round 3: Final predictions (parallel)
        if "round3" in checkpoint_data:
            print("\n[Round 3] Resuming from checkpoint...")
            round3 = checkpoint_data["round3"]
            _cb("debating_r3", 100, "Round 3 restored from checkpoint")
        else:
            print(f"\n{'#'*60}")
            print("Round 3: 最终预测 (并行)")
            print(f"{'#'*60}")
            _cb("debating_r3", 0, "Round 3 starting...")

            completed_count_r3 = 0
            total_agents = len(self.agents)

            def _run_round3(agent):
                nonlocal completed_count_r3
                try:
                    result = agent.final_predict(question, agent_contexts[agent.name], round2)
                    prob_str = f"{result['probability']}%" if result["probability"] is not None else "N/A"
                    print(f"  [{agent.name}] 最终预测: {prob_str}")
                    completed_count_r3 += 1
                    _cb(
                        "debating_r3",
                        int(completed_count_r3 / total_agents * 100),
                        f"Round 3: {agent.name} complete ({completed_count_r3}/{total_agents})",
                        current=completed_count_r3,
                        total=total_agents,
                        agent_name=agent.name,
                        data=result,
                    )
                    return result
                except Exception as e:
                    print(f"  [{agent.name}] 错误: {e}")
                    completed_count_r3 += 1
                    for r2 in round2:
                        if r2["agent_name"] == agent.name:
                            _cb(
                                "debating_r3",
                                int(completed_count_r3 / total_agents * 100),
                                f"Round 3: {agent.name} failed ({completed_count_r3}/{total_agents})",
                                current=completed_count_r3,
                                total=total_agents,
                                agent_name=agent.name,
                                data=r2,
                            )
                            return r2.copy()
                    fallback = {"agent_name": agent.name, "stance": agent.stance,
                                "probability": None, "reasoning": f"(失败: {e})", "raw_response": ""}
                    _cb(
                        "debating_r3",
                        int(completed_count_r3 / total_agents * 100),
                        f"Round 3: {agent.name} failed ({completed_count_r3}/{total_agents})",
                        current=completed_count_r3,
                        total=total_agents,
                        agent_name=agent.name,
                        data=fallback,
                    )
                    return fallback

            round3_by_agent = {}
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(_run_round3, a): a for a in self.agents}
                for future in as_completed(futures, timeout=300):
                    agent = futures[future]
                    try:
                        round3_by_agent[agent.name] = future.result(timeout=120)
                    except Exception as e:
                        print(f"  [{agent.name}] Round 3 timed out: {e}")
                        round3_by_agent[agent.name] = {
                            "agent_name": agent.name, "stance": agent.stance,
                            "probability": None, "reasoning": f"(超时: {e})", "raw_response": "",
                        }
            round3 = [round3_by_agent.get(a.name, {
                "agent_name": a.name, "stance": a.stance,
                "probability": None, "reasoning": "(未完成)", "raw_response": "",
            }) for a in self.agents]

            if checkpoint_manager is not None:
                checkpoint_data["round3"] = round3
                checkpoint_manager.save(question, checkpoint_data)

        # 5. Meta-predictions for BTS (parallel)
        if "meta_predictions" in checkpoint_data:
            print("\n[Meta-Prediction] Resuming from checkpoint...")
            meta_predictions = checkpoint_data["meta_predictions"]
            _cb("meta_predicting", 100, "Meta-predictions restored from checkpoint")
        else:
            print(f"\n{'#'*60}")
            print("Meta-Prediction: 元预测 (并行)")
            print(f"{'#'*60}")
            _cb("meta_predicting", 0, "Meta-predictions starting...")

            meta_predictions = {}
            completed_count_meta = 0
            total_meta = sum(1 for r3 in round3 if r3.get("probability") is not None)

            def _run_meta(agent, own_pred):
                nonlocal completed_count_meta
                try:
                    meta = agent.meta_predict(question, own_pred)
                    if meta is not None:
                        print(f"  [{agent.name}] 元预测 (预测平均值): {meta}%")
                    completed_count_meta += 1
                    _cb(
                        "meta_predicting",
                        int(completed_count_meta / max(total_meta, 1) * 100),
                        f"Meta: {agent.name} complete ({completed_count_meta}/{total_meta})",
                        current=completed_count_meta,
                        total=total_meta,
                        agent_name=agent.name,
                        data={"meta_prediction": meta},
                    )
                    return meta
                except Exception as e:
                    print(f"  [{agent.name}] 元预测失败: {e}")
                    completed_count_meta += 1
                    _cb(
                        "meta_predicting",
                        int(completed_count_meta / max(total_meta, 1) * 100),
                        f"Meta: {agent.name} failed ({completed_count_meta}/{total_meta})",
                        current=completed_count_meta,
                        total=total_meta,
                        agent_name=agent.name,
                        data={"meta_prediction": None},
                    )
                    return None

            with ThreadPoolExecutor(max_workers=3) as pool:
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

            if checkpoint_manager is not None:
                checkpoint_data["meta_predictions"] = meta_predictions
                checkpoint_manager.save(question, checkpoint_data)

        # 6. Aggregate with all mechanisms
        _cb("aggregating", 0, "Aggregation starting...")

        reputation_weights = self.reputation_tracker.get_weights()

        agg_results = {
            "simple_average": aggregate_simple_average(round3),
            "median": aggregate_median(round3),
            "trimmed_mean": aggregate_trimmed_mean(round3),
            "logit_average": aggregate_logit_average(round3),
            "extremized": aggregate_extremized(round3, d=Config.EXTREMIZATION_D),
            "reputation_weighted": aggregate_reputation_weighted(round3, reputation_weights),
            "lmsr_market": aggregate_lmsr(
                round3,
                budgets={name: 100.0 * (1 + w) for name, w in reputation_weights.items()},
                liquidity=Config.LMSR_LIQUIDITY,
            ),
            "peer_prediction": aggregate_peer_prediction(round3, meta_predictions or None),
            "hybrid": aggregate_hybrid(
                round3,
                reputation_weights=reputation_weights,
                meta_predictions=meta_predictions or None,
                lmsr_liquidity=Config.LMSR_LIQUIDITY,
                lambda_market=Config.HYBRID_LAMBDA_MARKET,
                lambda_reputation=Config.HYBRID_LAMBDA_REPUTATION,
                lambda_bts=Config.HYBRID_LAMBDA_BTS,
            ),
        }

        _cb("aggregating", 100, "Aggregation complete")

        # Backwards-compatible values
        avg_prob = agg_results["simple_average"]["probability"]

        # Round 1 average for no-debate comparison
        r1_valid = [r["probability"] for r in round1 if r["probability"] is not None]
        r1_avg = statistics.mean(r1_valid) if r1_valid else None

        result = {
            "question": question,
            "market_price": market_price,
            "timestamp": datetime.utcnow().isoformat(),
            "rag_sources": rag_result.get("sources", []),
            "document_count": len(documents),
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
            "entity_graph": entity_graph.to_dict() if entity_graph else None,
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

        _cb("completed", 100, "Debate pipeline complete", data=result)

        # Clean up checkpoint on successful completion
        if checkpoint_manager is not None:
            checkpoint_manager.clear(question)

        return result

