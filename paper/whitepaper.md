# Collective AI Deliberation: A Multi-Expert Consultation Framework for Human Opinion Refinement

**Version 1.0 | March 2026**

---

## Abstract

We present a multi-agent AI consultation framework that helps users refine their opinions through structured interaction with domain-specific AI expert clones. Unlike single-LLM chatbots that tend toward sycophancy, our system creates **structured cognitive conflict** by assembling a panel of 5 AI experts with diverse analytical perspectives, each enhanced with domain-specific knowledge profiles (Level 2 AI Cloning). Through a 4-phase consultation pipeline — independent evaluation, interactive dialogue, peer discussion, and final synthesis — the system identifies blind spots in user thinking, challenges cognitive biases, and produces actionable recommendations. We demonstrate the framework with two domain implementations: cryptocurrency investment analysis and sports prediction. Our approach combines techniques from mechanism design, retrieval-augmented generation (RAG), and multi-agent systems to create a consultation experience that is more balanced, rigorous, and informative than interacting with a single AI assistant.

---

## 1. Introduction

### 1.1 The Problem

Large Language Models (LLMs) have become the default tool for seeking advice and analysis. However, single-LLM interactions suffer from several well-documented limitations:

1. **Sycophancy**: LLMs tend to agree with the user's stated position, reinforcing existing biases rather than challenging them (Perez et al., 2023; Sharma et al., 2023).

2. **Perspective Homogeneity**: A single model provides one analytical lens. Complex decisions — investment strategies, career choices, policy judgments — require multiple perspectives that a single system prompt cannot adequately capture.

3. **No Structured Disagreement**: In human expert consultation (e.g., medical second opinions, investment committee decisions), disagreement among experts is a feature, not a bug. It surfaces assumptions, identifies risks, and leads to more calibrated judgments. Single-LLM interactions lack this mechanism.

4. **Shallow Domain Expertise**: General-purpose LLMs lack the specialized analytical frameworks, typical reasoning patterns, and domain-specific heuristics that characterize true domain experts.

### 1.2 Our Approach

We propose a **Collective AI Deliberation** framework that addresses these limitations through three key innovations:

- **Level 2 AI Cloning**: Each expert agent is enhanced with a domain-specific knowledge profile containing analytical frameworks, few-shot reasoning examples, and characteristic expression patterns. This transforms a generic LLM into a specialized expert clone with consistent analytical behavior.

- **Multi-Phase Consultation Pipeline**: A structured 4-phase process that separates independent evaluation (reducing groupthink), interactive dialogue (enabling user engagement), peer discussion (forcing cross-examination), and final synthesis (producing refined conclusions).

- **Designed Diversity**: Expert panels are constructed with intentionally diverse analytical stances (supportive, skeptical, cautious, neutral) to guarantee that multiple perspectives are represented, preventing the echo chamber effect.

### 1.3 Contributions

1. A novel AI expert cloning methodology (Level 2) that uses structured knowledge profiles with few-shot examples to create domain-specialized agents from general-purpose LLMs.
2. A multi-phase consultation pipeline with user-in-the-loop interaction design.
3. Two complete domain implementations (cryptocurrency and sports) demonstrating the framework's applicability.
4. An open-source reference implementation with Streamlit-based user interface.

---

## 2. Related Work

### 2.1 Multi-Agent LLM Systems

Recent work has explored using multiple LLM agents for improved reasoning. **LLM Debate** (Du et al., 2023) showed that multi-agent debate improves mathematical and factual reasoning. **Society of Mind** (Zhuge et al., 2023) demonstrated benefits of agent role specialization. **ChatEval** (Chan et al., 2023) used multi-agent debate for text evaluation. Our work extends these approaches from factual/reasoning tasks to **opinion refinement**, where the goal is not a single correct answer but a more calibrated, well-considered judgment.

### 2.2 AI-Assisted Decision Making

**Superforecasting** research (Tetlock & Gardner, 2015) demonstrated that structured analytical frameworks and diverse perspectives improve prediction accuracy. The **Delphi method** uses iterative expert consultation with controlled feedback. Our system computationally operationalizes these principles with AI agents replacing human experts while preserving the structured disagreement mechanism.

### 2.3 Prediction Markets and Mechanism Design

Our framework builds on mechanism design principles from prediction markets. **LMSR** (Hanson, 2003) provides a principled way to aggregate beliefs. **Bayesian Truth Serum** (Prelec, 2004) incentivizes honest reporting without requiring ground truth. **Reputation systems** track expert reliability over time. We adapt these mechanisms for the opinion consultation context.

### 2.4 Retrieval-Augmented Generation

**RAG** (Lewis et al., 2020) grounds LLM responses in retrieved evidence. **RAFT** (Zhang et al., 2024) trains models to distinguish relevant from irrelevant documents. Our system uses RAG to provide experts with current information while leveraging RAFT-style document evaluation to filter noise.

---

## 3. System Architecture

### 3.1 Overview

The system consists of four layers:

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface Layer                   │
│        Streamlit app with multi-phase interaction         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                 Consultation Engine                       │
│    ConsultationPipeline: 4-phase orchestration           │
│    ConsultAgent × 5: knowledge-enhanced expert clones    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               Knowledge & Cloning Layer                  │
│    Knowledge Profiles: frameworks + few-shots + style    │
│    Expert Panels: domain-specific expert configurations   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                Information Retrieval Layer                │
│    RAG: YouTube transcripts + Tavily news search         │
│    RAFT-style document mixing and evaluation             │
│    Information partitioning for asymmetry                 │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Design Principles

**P1: Structured Disagreement Over Consensus.** The system is designed to surface disagreement, not suppress it. Expert stances are pre-assigned to ensure multiple viewpoints.

**P2: User as Participant, Not Observer.** Unlike automated prediction systems, the user actively engages with experts in Phase 2, challenging and being challenged.

**P3: Knowledge-Grounded Expertise.** Each expert's analytical behavior is anchored in a concrete knowledge profile, not just a persona description.

**P4: Parallel Execution for Efficiency.** All phases use parallel execution (`ThreadPoolExecutor`) across agents to minimize latency.

---

## 4. Level 2 AI Cloning

### 4.1 Cloning Hierarchy

We define three levels of AI expert cloning:

| Level | Method | Persona Depth | Cost |
|-------|--------|--------------|------|
| **Level 1** | System prompt persona (name + description) | Shallow: same LLM, different hat | Low |
| **Level 2** | Knowledge profile injection (framework + few-shots + style) | Medium: consistent analytical behavior | Medium |
| **Level 3** | Fine-tuned model (LoRA adapter on expert corpus) | Deep: internalized expertise | High |

Level 1 is the approach used by most multi-agent systems — it provides surface-level role differentiation but agents quickly converge to similar reasoning patterns. Level 3 requires substantial training data and compute. **Level 2 is the practical sweet spot**: it provides meaningful behavioral differentiation without the cost of fine-tuning.

### 4.2 Knowledge Profile Structure

Each expert's knowledge profile is a structured markdown document containing:

```
# Expert Name — Knowledge Profile

## Archetype
Real-world expert/school of thought this clone is modeled after.

## Core Analytical Framework
### Key Analysis Dimensions
Numbered list of the expert's primary analytical tools and metrics.

### Core Principles/Beliefs
The expert's fundamental assumptions and biases.

## Few-shot Examples

### Example 1: [Scenario Type]
**Question/User Opinion**: [Input]
**Analysis**: [Full expert-style response demonstrating framework usage]

### Example 2: [Scenario Type]
...

### Example 3: [Scenario Type]
...

## Typical Phrases & Mannerisms
Characteristic expressions that maintain consistency.
```

### 4.3 Prompt Architecture

The `build_clone_prompt()` function assembles a 4-layer system prompt:

```
┌─────────────────────────────────┐
│ Layer 1: Identity               │  Expert name, role, expertise areas
├─────────────────────────────────┤
│ Layer 2: Knowledge Profile      │  ~80% of total prompt
│  - Analytical framework         │  Framework, examples, mannerisms
│  - 3 few-shot examples          │  loaded from markdown files
│  - Typical phrases              │
├─────────────────────────────────┤
│ Layer 3: Behavioral Rules       │  Stay in character, use framework,
│                                 │  be honest, give concrete advice
├─────────────────────────────────┤
│ Layer 4: RAG Context            │  Retrieved documents for current topic
└─────────────────────────────────┘
```

The knowledge profile constitutes approximately 80% of the system prompt, making the expert's analytical DNA the dominant signal in the LLM's context window.

### 4.4 Crypto Domain Expert Clones

| Expert | Archetype | Stance | Key Framework |
|--------|-----------|--------|---------------|
| 链上数据分析师 | Willy Woo / Glassnode | Neutral | MVRV, NUPL, exchange flows, on-chain metrics |
| 宏观经济学家 | Raoul Pal / Lyn Alden | Skeptical | Global liquidity cycles, real rates, debt/GDP |
| 加密原生研究员 | Arthur Hayes / Messari | Supportive | Narrative cycles, ecosystem metrics, halving |
| 风险管理顾问 | Nassim Taleb / Kelly Criterion | Cautious | Max drawdown, VaR, position sizing, volatility |
| 监管政策专家 | a16z Policy / Coin Center | Neutral | SEC actions, global regulatory framework, compliance |

### 4.5 Sports Domain Expert Clones

| Expert | Archetype | Stance | Key Framework |
|--------|-----------|--------|---------------|
| 数据统计专家 | FiveThirtyEight / Nate Silver | Neutral | ELO, Net Rating, Monte Carlo simulation, r² |
| 战术分析师 | Zach Lowe / Zonal Marking | Neutral | Matchup analysis, coaching adjustments, system fit |
| 伤病体能专家 | Sports medicine perspective | Cautious | Injury recurrence rates, load management, age curves |
| 博彩市场分析师 | Pinnacle / Sharp market theory | Neutral | CLV, implied probability, sharp vs public money |
| 资深体育评论员 | Bill Simmons / narrative school | Supportive | Historical analogies, championship DNA, intangibles |

---

## 5. Multi-Phase Consultation Pipeline

### 5.1 Pipeline Overview

```
User Input: topic + opinion + domain
         │
         ▼
    ┌─────────┐     RAG retrieval: YouTube transcripts
    │ Context  │──── + news articles, RAFT-style mixing
    │ Retrieval│     + information partitioning
    └────┬────┘
         │
         ▼
    ┌─────────┐     5 experts evaluate independently
    │ Phase 1 │──── Parallel execution (ThreadPoolExecutor)
    │ Evaluate│     Output: assessment, agree/challenge points,
    └────┬────┘     key insight, confidence score
         │
         ▼
    ┌─────────┐     User reads evaluations
    │ Phase 2 │──── User chats 1-on-1 with experts
    │ Interact│     Conversation history maintained
    └────┬────┘     User advances when satisfied
         │
         ▼
    ┌─────────┐     Each expert sees all others' evaluations
    │ Phase 3 │──── Experts respond, update, identify blind spots
    │ Discuss │     Parallel execution
    └────┬────┘
         │
         ▼
    ┌─────────┐     Each expert gives final assessment
    │ Phase 4 │──── Recommendations + risk warnings
    │ Finalize│     Confidence tracking (Phase 1 → Phase 4)
    └────┬────┘
         │
         ▼
    ┌─────────┐     Aggregate insights, blind spots,
    │ Report  │──── recommendations, risk warnings
    │Synthesis│     Confidence shift visualization
    └─────────┘
```

### 5.2 Phase 1: Independent Evaluation

Each expert independently evaluates the user's opinion without seeing other experts' views. This prevents anchoring and groupthink.

**Input**: Topic, user opinion, RAG context (expert-specific via information partitioning)

**Output structure**:
- `ASSESSMENT`: Overall evaluation (support / partial support / oppose)
- `AGREE_POINTS`: What the expert agrees with and why
- `CHALLENGE_POINTS`: What the expert challenges with evidence
- `KEY_INSIGHT`: Most important thing the user should know
- `CONFIDENCE`: 0-100% confidence in the assessment

**Design rationale**: By requiring structured agreement AND disagreement, we prevent the sycophancy failure mode. The expert must find something to challenge even if they largely agree.

### 5.3 Phase 2: Interactive Dialogue

The user reads all Phase 1 evaluations and can engage in free-form conversation with any expert. This is the **user-in-the-loop** component that distinguishes our system from fully automated multi-agent debates.

**Key features**:
- Per-expert conversation history is maintained
- Expert responses are context-aware (topic + original opinion + conversation history)
- No forced structure — the user drives the conversation depth

**Design rationale**: Users often have follow-up questions or want to challenge specific expert claims. This phase allows the user to test the robustness of expert reasoning.

### 5.4 Phase 3: Expert Discussion

Experts review each other's Phase 1 evaluations and engage in structured peer discussion.

**Input**: Each expert sees ALL other experts' evaluations (but not their own — they already have it)

**Output structure**:
- `RESPONSES`: Per-expert targeted responses ("Re: [Expert]: [Response]")
- `UPDATED_ASSESSMENT`: Revised view after considering peers
- `BLIND_SPOTS`: Issues not yet adequately addressed
- `CONFIDENCE`: Updated confidence score

**Design rationale**: Expert-to-expert discussion forces cross-examination. An expert who was overly confident must address challenges from peers. An expert who missed a factor must acknowledge it. This mimics the dynamics of a real expert committee.

### 5.5 Phase 4: Final Assessment

After the full discussion, each expert gives their final assessment incorporating all information from Phases 1-3.

**Output structure**:
- `FINAL_ASSESSMENT`: 2-3 sentence conclusive evaluation
- `RECOMMENDATION`: Concrete, actionable advice
- `RISK_WARNING`: 1-2 key risks the user should monitor
- `CONFIDENCE`: Final confidence score

### 5.6 Report Synthesis

The system aggregates all Phase 4 outputs into a structured consultation report:

1. **Expert Panel Summary**: Each expert's final assessment
2. **Key Insights**: Unique insights from each expert's domain
3. **Blind Spots**: Issues identified during discussion
4. **Recommendations**: Actionable items from all experts
5. **Risk Warnings**: Consensus and divergent risk assessments
6. **Confidence Shift**: How expert confidence changed from Phase 1 to Phase 4

---

## 6. Information Retrieval and Grounding

### 6.1 RAG Pipeline

The system retrieves current information to ground expert analysis:

1. **YouTube Transcript Retrieval**: Searches for videos related to the topic, extracts full transcripts via `YouTubeTranscriptApi`. Longer videos (indicating deeper analysis) are prioritized.

2. **News Search**: Tavily API provides recent news articles for supplementary context.

3. **RAFT-style Document Mixing**: Documents are split into "oracle" (high-quality, relevant) and "distractor" (potentially irrelevant) categories, then shuffled. Experts must evaluate document relevance as part of their analysis.

### 6.2 Information Partitioning

To create genuine information asymmetry among experts:

```
Total documents
    ├── 40% → Shared pool (all experts see these)
    └── 60% → Private pool
                ├── Agent 1: 2 exclusive documents
                ├── Agent 2: 2 exclusive documents
                ├── Agent 3: 2 exclusive documents
                ├── Agent 4: 2 exclusive documents
                └── Agent 5: 2 exclusive documents
```

This ensures experts have different information bases, making their independent evaluations genuinely diverse rather than superficially diverse.

---

## 7. Technical Implementation

### 7.1 System Requirements

- **Python 3.11+**
- **LLM Backends**: DeepSeek V3 (primary), with optional OpenAI GPT-4o, Anthropic Claude, Google Gemini
- **APIs**: Tavily (news search), YouTube Data API (transcript retrieval)
- **Frontend**: Streamlit with Plotly for visualization
- **Execution**: ThreadPoolExecutor for parallel agent execution

### 7.2 Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `ConsultAgent` | `consult_agent.py` | Individual expert agent with 4-phase methods |
| `ConsultationPipeline` | `consultation.py` | Pipeline orchestration and report synthesis |
| `build_clone_prompt` | `knowledge_loader.py` | Level 2 knowledge profile injection |
| `Expert Panels` | `expert_panels.py` | Domain-specific expert configurations |
| `NewsRetriever` | `retriever.py` | RAG pipeline (YouTube + news) |
| `partition_documents` | `info_partition.py` | Information asymmetry creation |
| Streamlit App | `app_consult.py` | User interface and session management |

### 7.3 Multi-Model Distribution

Agents are distributed across available LLM backends in round-robin fashion:

```python
for i, expert in enumerate(panel):
    backend = backends[i % len(backends)] if backends else None
    agents.append(ConsultAgent(**expert, backend=backend))
```

This provides:
- **Diversity of reasoning**: Different LLMs have different reasoning patterns
- **Cost optimization**: Mix expensive and affordable models
- **Rate limit management**: Distribute API calls across providers
- **Resilience**: If one backend fails, others continue

### 7.4 Parallel Execution

All phases use `ThreadPoolExecutor` with `max_workers=len(agents)` for full parallelism:

```python
with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
    futures = {pool.submit(_run, a): a for a in self.agents}
    for future in as_completed(futures):
        agent = futures[future]
        results[agent.name] = future.result()
```

Typical wall-clock time for a full consultation: 2-4 minutes (vs. 10-20 minutes sequential).

---

## 8. Use Cases

### 8.1 Cryptocurrency Investment Analysis

**Scenario**: A user believes "Bitcoin will reach $150,000 this year due to ETF inflows and the halving effect."

**Expert responses (illustrative)**:

- **链上数据分析师**: "MVRV Z-Score at 2.8 suggests room for upside, but LTH supply distribution hasn't reached typical top-cycle patterns. The $150K target requires sustained supply contraction."

- **宏观经济学家**: "ETF inflows are demand-side positive, but $150K implies global liquidity expansion that isn't guaranteed. If inflation rebounds, rate cut expectations — a key BTC driver — could collapse."

- **风险管理顾问**: "Historical max drawdowns of 77-93% mean you should ask: 'Can I hold through a 50% drop on the way to $150K?' Position sizing matters more than price targets."

- **监管政策专家**: "The ETF approval was a milestone, but ongoing SEC litigation against exchanges creates regulatory uncertainty. A surprise enforcement action could trigger a 20%+ correction."

**Value delivered**: The user's thesis isn't wrong, but they learn about supply-side constraints, macro dependencies, position sizing risks, and regulatory tail risks they hadn't considered.

### 8.2 Sports Prediction Analysis

**Scenario**: A user believes "The Lakers will definitely make the playoffs because they have LeBron."

**Expert responses (illustrative)**:

- **数据统计专家**: "Current Net Rating of +1.2 implies ~62% playoff probability. Not 'definitely' — nearly 4 in 10 simulations have them missing."

- **伤病体能专家**: "AD's 27% career absence rate is the key variable. When AD is out, the team's Net Rating drops by 10 points — from playoff team to lottery team."

- **博彩市场分析师**: "The market has them at -150 to make playoffs (implied 60%). If you think 'definitely' (>90%), the market disagrees by 30 percentage points."

- **资深体育评论员**: "Having a star doesn't guarantee playoffs — see 2019 Lakers (LeBron, 33-49 record). System fit and health matter as much as talent."

**Value delivered**: The user's confidence is calibrated from "definitely" (~95%) to a more realistic 60-65%, with specific variables to monitor.

---

## 9. Evaluation Framework

### 9.1 Proposed Metrics

We propose evaluating the framework across three dimensions:

**1. Opinion Calibration**
- Measure user confidence before and after consultation
- For verifiable predictions: compare user's post-consultation confidence to actual outcomes using Brier Score
- Target: post-consultation Brier Score < pre-consultation Brier Score

**2. Blind Spot Discovery**
- Count unique risk factors / considerations identified by experts that the user hadn't mentioned
- Measure user acknowledgment of new factors in Phase 2 interactions
- Target: ≥ 3 new considerations per consultation

**3. Expert Diversity**
- Measure inter-expert agreement (lower = more diverse perspectives)
- Track confidence spread across experts
- Measure stance coverage: all 4 stance types represented in the output
- Target: no two experts give identical assessments

### 9.2 Comparison Baselines

| Baseline | Description |
|----------|-------------|
| Single LLM | Same question to one LLM instance |
| Single LLM + "Devil's Advocate" prompt | One LLM asked to challenge the user |
| Level 1 Multi-Agent | 5 agents with persona descriptions only (no knowledge profiles) |
| **Our System (Level 2)** | 5 agents with knowledge profiles + 4-phase pipeline |

### 9.3 Experimental Design (Proposed)

1. **Dataset**: 50 verifiable prediction questions (25 crypto, 25 sports) with known outcomes
2. **Participants**: Simulated users with pre-set opinions (varying accuracy)
3. **Metrics**: Pre/post Brier Score, blind spot count, expert diversity index
4. **Hypothesis**: Level 2 cloning + multi-phase pipeline produces better calibration than all baselines

---

## 10. Limitations and Future Work

### 10.1 Current Limitations

1. **Knowledge Profile Staleness**: Few-shot examples in knowledge profiles are static. They don't update with market conditions or new events.

2. **No Ground Truth Feedback Loop**: The system doesn't track whether its advice led to better outcomes. A feedback mechanism would enable Level 3 cloning via fine-tuning.

3. **Language**: Current implementation is Chinese-language. Internationalization would expand the user base.

4. **Expert Selection**: Panels are pre-defined per domain. Ideally, the system would dynamically select experts based on the specific topic.

5. **Cost**: A full 4-phase consultation with 5 experts requires ~40 LLM calls (5 agents × 4 phases × 2 including meta). At current API prices, this is $0.05-0.50 per consultation depending on model.

### 10.2 Future Directions

**Level 3 Cloning**: Fine-tune LoRA adapters on curated expert corpora (e.g., all Arthur Hayes blog posts, all Willy Woo Twitter threads) for deeper behavioral fidelity.

**Dynamic Expert Selection**: Use a classifier to analyze the user's topic and automatically compose the optimal expert panel from a larger pool.

**Persistent Expert Memory**: Each expert maintains memory across consultations — remembering their past predictions, tracking their accuracy, and adjusting confidence accordingly. This connects to the existing `ReputationTracker` from the prediction market system.

**Cognitive Bias Detection**: Automatically detect confirmation bias (user only engages with agreeing experts), anchoring (user opinion doesn't change despite strong counter-evidence), and authority bias (user only trusts highest-confidence expert).

**Multi-Turn Consultation**: Allow users to return with updated opinions after real-world developments, creating a longitudinal consultation record.

**Aggregation Mechanisms**: Integrate the LMSR, BTS, and reputation-weighted aggregation from the original prediction market system to produce a mathematically grounded "consensus score" alongside the qualitative report.

---

## 11. Conclusion

We have presented a multi-agent AI consultation framework that transforms the single-LLM advice paradigm into a structured expert panel experience. Through Level 2 AI Cloning (knowledge profile injection with few-shot examples), a 4-phase consultation pipeline (evaluate → interact → discuss → finalize), and designed diversity (varied expert stances and information asymmetry), the system produces richer, more balanced, and more actionable advice than any single AI interaction.

The framework is domain-agnostic — while we demonstrate cryptocurrency and sports implementations, the architecture supports any domain where expert consultation adds value: medical second opinions, legal strategy, career decisions, policy analysis, and more.

By making high-quality multi-expert consultation accessible to anyone, we aim to democratize the kind of structured analytical thinking that was previously available only to those with access to expensive human expert networks.

---

## References

- Chan, C. M., et al. (2023). ChatEval: Towards Better LLM-based Evaluators through Multi-Agent Debate. *arXiv:2308.07201*.
- Du, Y., et al. (2023). Improving Factuality and Reasoning in Language Models through Multiagent Debate. *arXiv:2305.14325*.
- Hanson, R. (2003). Combinatorial Information Market Design. *Information Systems Frontiers*, 5(1), 107-119.
- Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*.
- Perez, E., et al. (2023). Discovering Language Model Behaviors with Model-Written Evaluations. *ACL 2023*.
- Prelec, D. (2004). A Bayesian Truth Serum for Subjective Data. *Science*, 306(5695), 462-466.
- Sharma, M., et al. (2023). Towards Understanding Sycophancy in Language Models. *arXiv:2310.13548*.
- Tetlock, P. E., & Gardner, D. (2015). *Superforecasting: The Art and Science of Prediction*. Crown.
- Zhang, T., et al. (2024). RAFT: Adapting Language Model to Domain Specific RAG. *arXiv:2403.10131*.
- Zhuge, M., et al. (2023). Mindstorms in Natural Language-Based Societies of Mind. *arXiv:2305.17066*.

---

## Appendix A: Knowledge Profile Example (Abbreviated)

**Expert**: 风险管理顾问 (Risk Management Consultant)
**Archetype**: Nassim Taleb's tail-risk thinking + Kelly Criterion

**Core Framework**:
1. Volatility analysis (historical vol, implied vol, ATR)
2. Drawdown analysis (MDD, recovery time)
3. Position sizing (Kelly Criterion, VaR/CVaR)
4. Correlation risk (dynamic correlation, tail correlation)
5. Liquidity risk (spread, depth, slippage)
6. Extreme scenarios (black swans, counterparty risk)

**Few-shot Example** (abbreviated):

> **User**: "I plan to allocate 50% of my portfolio to Bitcoin"
>
> **Expert Response**: "Let me quantify what this means with risk data. Bitcoin's annualized volatility is 60-80% (vs S&P 500 at 15-18%). A 50% allocation creates portfolio volatility of 30-40%. Historical drawdowns: -93% (2011), -86% (2014), -84% (2018), -77% (2022). At 50% allocation, a -77% BTC drawdown means -38.5% total portfolio loss. Kelly Criterion suggests optimal allocation of ~30% (half-Kelly for parameter uncertainty). Recommendation: max 20-30%, build position over 3-6 months, set portfolio-level max drawdown tolerance."

**Typical Phrases**:
- "Let me show you what this means in numbers"
- "If you're wrong, what's the worst case?"
- "Position sizing matters 10x more than direction"

---

## Appendix B: System Prompt Composition

```
Total system prompt: ~3,000-3,500 characters per expert

Composition:
├── Layer 1 (Identity):        ~150 chars  (5%)
├── Layer 2 (Knowledge Profile): ~2,500 chars (80%)
│   ├── Archetype:              ~100 chars
│   ├── Framework:              ~500 chars
│   ├── Few-shot Examples (×3): ~1,500 chars
│   └── Typical Phrases:        ~400 chars
├── Layer 3 (Behavioral Rules): ~300 chars  (10%)
└── Layer 4 (RAG Context):      Variable    (5%+)
```

---

## Appendix C: API Cost Estimation

| Phase | LLM Calls | Avg Tokens/Call | Est. Cost (DeepSeek V3) |
|-------|-----------|-----------------|------------------------|
| Phase 1 (Evaluate) | 5 | ~3,000 in + ~800 out | $0.005 |
| Phase 2 (Chat, avg 2 turns × 2 experts) | 4 | ~3,500 in + ~500 out | $0.004 |
| Phase 3 (Discuss) | 5 | ~4,000 in + ~800 out | $0.006 |
| Phase 4 (Final) | 5 | ~4,500 in + ~500 out | $0.006 |
| RAG Retrieval | 1 | — | $0.001 (Tavily) |
| **Total** | **~20** | | **~$0.02** |

At DeepSeek V3 pricing ($0.27/M input, $1.10/M output), a full consultation costs approximately $0.02 — orders of magnitude cheaper than human expert consultation ($200-500/hour).

---

*This whitepaper describes the Collective AI Deliberation framework as implemented in the open-source prediction-market-debater project.*
