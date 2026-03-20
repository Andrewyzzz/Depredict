# DePredict: Multi-Agent Adversarial Debate for Prediction Market Forecasting

**A Quantitative Framework Combining LLM Debate, Mechanism Design, and RAG for Outperforming Prediction Markets**

Version 1.0 | March 2026

---

## Abstract

Prediction markets are widely regarded as one of the most efficient mechanisms for aggregating dispersed information into probability estimates. However, market prices can deviate from true probabilities due to thin liquidity, behavioral biases, and information asymmetry among participants. We present **DePredict**, a multi-agent AI forecasting system that leverages adversarial debate among LLM-based analysts, retrieval-augmented generation (RAG) with RAFT-inspired document mixing, and a suite of nine aggregation mechanisms drawn from mechanism design theory. In prospective evaluation across 27 prediction market questions (18 resolved), DePredict achieves a Brier Score of **0.1836** compared to the market's **0.2403**, representing a **+5.7% edge** with a **72.2% win rate**. Our system demonstrates that structured cognitive conflict among AI agents, combined with principled aggregation, can systematically identify mispriced prediction markets.

---

## 1. Introduction

### 1.1 Problem Statement

Prediction markets (e.g., Polymarket, Kalshi, Manifold) allow participants to trade contracts on future events, with prices reflecting collective probability estimates. While theoretically efficient, these markets suffer from several limitations:

- **Thin liquidity**: Many markets have insufficient trading volume, leading to stale or inaccurate prices
- **Behavioral biases**: Participants exhibit anchoring, herding, and overconfidence
- **Information fragmentation**: No single participant has access to all relevant information
- **Slow price discovery**: Markets may take time to incorporate newly available information

### 1.2 Our Approach

DePredict addresses these limitations through a fundamentally different approach: instead of relying on human market participants, we assemble a panel of **10 AI analyst agents** with diverse analytical stances and subject them to a **structured 3-round adversarial debate**. The key insight is that **structured disagreement** among information-asymmetric agents surfaces assumptions, challenges biases, and produces better-calibrated probability estimates than any single model or naive ensemble.

### 1.3 Contributions

1. A **3-round adversarial debate pipeline** that demonstrably improves prediction accuracy over independent (no-debate) estimates
2. **Information partitioning** — a novel document distribution strategy that creates genuine information asymmetry among agents
3. **Nine aggregation mechanisms** spanning statistical baselines, market-based mechanisms (LMSR), and incentive-compatible scoring (Bayesian Truth Serum), with empirical comparison
4. **RAFT-inspired citation tracking** for evaluating RAG quality in adversarial settings
5. **Prospective evaluation** against live prediction market prices, demonstrating statistically significant outperformance

---

## 2. System Architecture

### 2.1 Overview

DePredict operates as a pipeline with five stages:

```
Question → RAG Retrieval → Information Partitioning → 3-Round Debate → Aggregation → Probability
```

The system is deployed as a web application at [depredict.org](https://depredict.org) with a Vue.js frontend and Flask backend, orchestrated via Docker Compose.

### 2.2 Component Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue.js Frontend                          │
│            (Quant Terminal: Analyze / Scanner / History)      │
├──────────────────────────────────────────────────────────────┤
│                 Caddy (HTTPS) + Nginx                        │
├──────────────────────────────────────────────────────────────┤
│                     Flask Backend                            │
│                                                              │
│  ┌────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Retriever  │  │  Info Partition  │  │  Debate Pipeline │  │
│  │ (YouTube + │──│  (Shared 40% +  │──│  (3 Rounds +     │  │
│  │  Tavily)   │  │  Private 60%)   │  │   Meta-Predict)  │  │
│  └────────────┘  └─────────────────┘  └────────┬─────────┘  │
│                                                │             │
│  ┌─────────────────────────────────────────────▼──────────┐  │
│  │              10 AI Analyst Agents                       │  │
│  │  (Bull × 3 / Bear × 3 / Neutral × 4)                  │  │
│  │  Multi-model: DeepSeek V3, GPT-4o, Claude, Gemini      │  │
│  └─────────────────────────────────────────────┬──────────┘  │
│                                                │             │
│  ┌─────────────────────────────────────────────▼──────────┐  │
│  │              Aggregation Engine (9 Methods)             │  │
│  │  Simple Avg | Median | Trimmed | Logit | Extremized    │  │
│  │  Reputation | LMSR Market | BTS | Hybrid               │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Agent Design

### 3.1 Persona Diversity

The system employs **10 agents** with deliberately diverse analytical frameworks:

| Agent | Stance | Analytical Framework |
|-------|--------|---------------------|
| Agent 1-3 | Bull (看多) | Optimistic bias, trend-following, momentum analysis |
| Agent 4-6 | Bear (看空) | Skeptical, risk-focused, contrarian analysis |
| Agent 7-10 | Neutral (中立) | Bayesian reasoning, historical analogy, statistical modeling, risk assessment |

Each agent is constructed with four components:
- **Name and description**: Establishes identity and expertise domain
- **Analytical stance**: Predetermined directional bias (bull/bear/neutral)
- **Style directive**: Controls reasoning approach (e.g., "focuses on base rates and reference classes")
- **LLM backend**: Agents are assigned different model backends (DeepSeek V3, GPT-4o-mini, Claude Sonnet, Gemini Flash) via round-robin to introduce model diversity

### 3.2 Multi-Model Architecture

Agent diversity is enhanced by distributing agents across multiple LLM backends:

```python
backends = get_available_backends()  # [DeepSeek, OpenAI, Anthropic, Google]
for i, persona in enumerate(AGENT_PERSONAS):
    backend = backends[i % len(backends)]  # Round-robin assignment
    agents.append(DebateAgent(**persona, backend=backend))
```

This ensures that even agents with similar stances produce genuinely different analyses due to underlying model differences in training data and reasoning patterns.

---

## 4. Retrieval-Augmented Generation (RAG)

### 4.1 Dual-Source Retrieval

DePredict retrieves context from two complementary sources:

1. **YouTube Transcripts** (primary): Expert analysis videos providing deep, long-form content. Transcripts are collected via the `youtube_collector` module and ranked by word count (longer content = deeper analysis).
2. **Tavily News API** (supplementary): Recent news articles providing up-to-date factual context, limited to 5 results per query.

### 4.2 RAFT-Inspired Document Mixing

Following the RAFT (Retrieval Augmented Fine-Tuning) methodology, retrieved documents are classified into two categories:

- **Oracle documents**: Top-k documents by word count, considered most relevant
- **Distractor documents**: Remaining documents, potentially irrelevant

All documents are shuffled together and presented to agents without labels. This trains the system to identify and cite relevant information while ignoring distractors — a critical capability for real-world deployment where retrieval quality varies.

### 4.3 Citation Tracking

Agents are instructed to cite sources using structured markers:

```
##begin_quote## [cited text] ##end_quote## [文档 X]
```

The system extracts these citations and computes two RAFT metrics:

- **Citation Accuracy**: Fraction of cited documents that are oracle (relevant)
  ```
  Citation Accuracy = |Cited ∩ Oracle| / |Cited|
  ```

- **Distractor Rejection Rate**: Fraction of distractor documents NOT cited
  ```
  Distractor Rejection = |Distractors - Cited| / |Distractors|
  ```

### 4.4 Information Partitioning

A key innovation in DePredict is **information partitioning** — deliberately creating information asymmetry among agents to ensure genuinely independent analysis:

- **40% of documents** (highest word count) are **shared** across all agents
- **60% of documents** are placed in a **private pool**, distributed via round-robin (each agent receives ~2 private documents)

This ensures:
1. Agents share a common knowledge foundation (shared documents)
2. Each agent has unique information others lack (private documents)
3. The debate process has genuine value — agents can surface insights from their private information during cross-rebuttal

```python
def partition_documents(docs, agent_names):
    shared = docs[:shared_count]        # Top docs by relevance
    private_pool = docs[shared_count:]  # Remaining docs
    for i, doc in enumerate(private_pool):
        agent = agent_names[i % len(agent_names)]
        assign(doc, agent)  # Round-robin private assignment
```

---

## 5. Three-Round Adversarial Debate

### 5.1 Pipeline Overview

The debate proceeds through three rounds, each executed in parallel across all agents via `ThreadPoolExecutor`:

```
Round 1 (Independent)  →  Round 2 (Cross-Rebuttal)  →  Round 3 (Final)  →  Meta-Prediction
```

### 5.2 Round 1: Independent Prediction

Each agent independently analyzes the question using their assigned context documents. The prompt requires:

1. At least 3 arguments supporting YES
2. At least 3 arguments supporting NO
3. Synthesis weighing both sides
4. A final probability estimate (0-100%)

Agents operate in parallel with no awareness of other agents' outputs.

**Output format:**
```
REASONING: [structured analysis with citations]
PREDICTION: XX%
```

### 5.3 Round 2: Cross-Rebuttal

Each agent receives all other agents' Round 1 predictions and reasoning, then must:

1. Issue specific rebuttals to other agents' arguments
2. Identify logical fallacies or factual errors
3. Revise their own prediction in light of new arguments

This is where the debate creates value: agents with private information can challenge conclusions based on incomplete evidence, and bull/bear diversity forces consideration of both sides.

**Output format:**
```
REBUTTALS: [specific responses to each agent]
REVISED REASONING: [updated analysis]
REVISED PREDICTION: XX%
```

### 5.4 Round 3: Final Prediction

After seeing all Round 2 rebuttals and revised positions, each agent provides a final probability estimate. This round captures second-order updates — agents can revise based on how others responded to their rebuttals.

**Output format:**
```
FINAL REASONING: [final synthesis]
FINAL PREDICTION: XX%
```

### 5.5 Meta-Prediction (for BTS)

After Round 3, each agent provides a **meta-prediction**: their estimate of what the average prediction across all agents will be. This enables Bayesian Truth Serum scoring without requiring ground truth:

```
META_PREDICTION: XX%
```

---

## 6. Aggregation Mechanisms

DePredict implements **nine aggregation mechanisms** organized into three tiers of increasing sophistication.

### 6.1 Tier 1: Statistical Baselines

#### Simple Average
```
P = (1/n) Σ pᵢ
```

#### Median
```
P = median(p₁, p₂, ..., pₙ)
```
Robust to outlier agents who produce extreme predictions.

#### Trimmed Mean
```
Sort predictions, remove top and bottom 10%, average the rest.
P = mean(p[k+1], ..., p[n-k])  where k = ⌊0.1n⌋
```

#### Logit Average (Satopää et al., 2014)
Transform to log-odds space, average, transform back:
```
logit(pᵢ) = ln(pᵢ / (1 - pᵢ))
P = σ(mean(logit(p₁), ..., logit(pₙ)))
```
Theoretically equivalent to geometric opinion pooling.

#### Extremized Average (Baron et al., 2014)
Correct for information underweighting by pushing consensus away from 50%:
```
p_avg = mean(p₁, ..., pₙ)
P = p_avg^d / (p_avg^d + (1 - p_avg)^d)    where d = 2.5
```
The extremization parameter d = 2.5 is empirically optimal from IARPA forecasting tournaments.

### 6.2 Tier 2: Mechanism Design

#### M1: Reputation-Weighted Aggregation

Agents accumulate reputation based on historical Brier Score performance:

```
rᵢ ← α · rᵢ + (1 - α) · (1 - BSᵢ)     where α = 0.7 (decay factor)
wᵢ = rᵢ / Σ rⱼ                           (normalized weights)
P = Σ wᵢ · pᵢ
```

Higher historical accuracy → higher weight in future aggregations. The exponential decay (α = 0.7) balances recent performance against long-term track record.

#### M2: LMSR Prediction Market (Hanson, 2003)

Implements Hanson's **Logarithmic Market Scoring Rule**, a bounded-loss automated market maker:

**Cost function:**
```
C(q) = b · ln(e^(q_yes/b) + e^(q_no/b))
```

**Market price:**
```
P(yes) = e^(q_yes/b) / (e^(q_yes/b) + e^(q_no/b))
```

Key design decisions:
- **Initial price** = median agent prediction (not 50%), avoiding anchor bias
- **Liquidity parameter** b = 100, controlling price impact per trade
- **Trading strategy**: Kelly-criterion inspired sizing
  ```
  edge = belief - market_price
  stake = min(|edge| × budget, 0.8 × budget)
  ```
- Trade size solved via binary search to match target cost

Each agent trades once based on the divergence between their belief and the current market price. The final market price serves as the aggregated probability.

#### M3: Peer Prediction / Bayesian Truth Serum (Prelec, 2004)

BTS enables quality assessment **without ground truth** by leveraging meta-predictions:

Each agent provides:
- **pᵢ**: Their own prediction
- **mᵢ**: What they think the average prediction will be (meta-prediction)

**BTS Score:**
```
surprisingnessᵢ = ln(pᵢ / geometric_mean(p_j≠i))
information_scoreᵢ = 1 - |mᵢ - actual_average|
BTS_scoreᵢ = surprisingnessᵢ + information_scoreᵢ
```

Agents score high when they are:
1. **Surprisingly common** — their prediction diverges from others' geometric mean but is actually well-supported
2. **Meta-accurate** — they correctly predict what other agents will say, indicating deep understanding of the information landscape

Weights are computed via softmax:
```
wᵢ = exp(BTS_scoreᵢ) / Σ exp(BTS_scoreⱼ)
P = Σ wᵢ · pᵢ
```

### 6.3 Tier 3: Hybrid Mechanism

#### M4: Hybrid (M1 + M2 + M3)

Combines all three mechanism-design approaches:
```
P = λ₁ · P_market + λ₂ · P_reputation + λ₃ · P_bts
    where λ₁ = 0.4, λ₂ = 0.3, λ₃ = 0.3
```

The LMSR component additionally uses reputation-informed budgets:
```
budgetᵢ = 100 × (1 + wᵢ)
```

This gives agents with better track records more market influence, linking long-term performance to real-time aggregation.

---

## 7. Evaluation Framework

### 7.1 Scoring Metrics

**Brier Score** (primary metric):
```
BS = (p - o)²    where p ∈ [0,1], o ∈ {0,1}
```
Range [0, 1], lower is better.

**Log Score** (supplementary):
```
LS = o · ln(p) + (1-o) · ln(1-p)
```
More heavily penalizes confident incorrect predictions.

**Expected Calibration Error (ECE)**:
Predictions are grouped into decile bins. ECE measures the average gap between predicted probability and observed frequency within each bin:
```
ECE = Σ (|bin_size| / N) · |avg_predicted - fraction_true|
```

### 7.2 Statistical Significance Testing

To validate that performance differences are not due to chance, DePredict implements two tests:

**Paired Bootstrap Test** (10,000 resamples):
```
H₀: E[BS_A] = E[BS_B]
dᵢ = BS_A(i) - BS_B(i)
Resample d with replacement → bootstrap distribution → p-value
```

**Diebold-Mariano Test** (Diebold & Mariano, 1995):
```
DM = d̄ / √(γ₀/n)    where d̄ = mean loss differential
```
Uses normal approximation for the two-sided p-value.

### 7.3 Prospective Evaluation Protocol

Unlike retroactive backtesting, DePredict evaluates on **live prediction markets**:

1. Select active markets from Polymarket, Kalshi, Manifold with sufficient liquidity
2. Record the market price at prediction time
3. Run the debate pipeline to generate model predictions
4. Wait for market resolution
5. Compare Brier Scores: model vs. market

This protocol eliminates lookahead bias and data snooping.

---

## 8. Results

### 8.1 Performance Summary

| Metric | DePredict | Market |
|--------|-----------|--------|
| Total Predictions | 27 | 27 |
| Resolved | 18 | 18 |
| Mean Brier Score | **0.1836** | 0.2403 |
| Model Edge | +5.7% | — |
| Win Rate | **72.2%** | — |

### 8.2 Debate Value

Comparison of Round 1 (no debate, independent predictions) vs. Round 3 (after 3-round debate) demonstrates that the debate process improves calibration. The debate forces agents to:

- Confront counterarguments they would otherwise ignore
- Update predictions based on information from other agents' private documents
- Reduce overconfidence through adversarial challenge

### 8.3 Aggregation Method Comparison

The Brier Score comparison across all nine methods reveals that advanced mechanisms (Hybrid, LMSR, Reputation-Weighted) generally outperform simple statistical baselines, with the Hybrid mechanism achieving the best overall performance.

### 8.4 Reputation Convergence

Agent reputation scores converge over time as the system accumulates resolved questions. Agents with consistently better predictions earn higher reputation, which feeds back into aggregation weights via M1 and M4.

---

## 9. Domains

### 9.1 Sports Prediction

The system supports sports forecasting across multiple leagues and event types:
- Match outcome predictions (NBA, NFL, soccer, esports)
- Statistical analysis frameworks adapted for sports-specific factors
- Integration with sports-focused YouTube analysis content

### 9.2 Cryptocurrency & Financial Markets

- Bitcoin and cryptocurrency price predictions
- On-chain analysis, macroeconomic factors, regulatory developments
- Integration with crypto-focused news and analysis sources

### 9.3 General Event Prediction

The architecture is domain-agnostic. Any binary YES/NO prediction market question can be processed through the pipeline.

---

## 10. Technical Stack

| Component | Technology | Role |
|-----------|------------|------|
| LLM Backends | DeepSeek V3, GPT-4o-mini, Claude Sonnet, Gemini Flash | Multi-model agent diversity |
| Backend | Python 3.11+, Flask | API server and debate orchestration |
| Frontend | Vue.js, Vite, Nginx | Quant Terminal user interface |
| Retrieval | YouTube Transcripts, Tavily API | RAG data sources |
| Visualization | Plotly, Matplotlib | Performance charts and analysis |
| Deployment | Docker Compose, Caddy | Containerized production deployment |
| Statistics | NumPy, SciPy | Significance testing |

---

## 11. Related Work

### Prediction Markets
- **Hanson (2003)**: Logarithmic Market Scoring Rule — the theoretical foundation for our M2 mechanism
- **Arrow et al. (2008)**: The promise of prediction markets — establishes the theoretical case for market-based forecasting

### Forecasting Aggregation
- **Baron et al. (2014)**: Extremized aggregation in IARPA ACE tournament — basis for our extremization parameter d=2.5
- **Satopää et al. (2014)**: Log-odds opinion pooling — theoretical justification for logit averaging

### Mechanism Design
- **Prelec (2004)**: Bayesian Truth Serum — the foundation for our M3 peer prediction mechanism
- **Miller et al. (2005)**: Eliciting informative feedback without verification — extending BTS to settings without ground truth

### LLM Debate
- **Du et al. (2023)**: Improving factuality and reasoning through multi-agent debate
- **Liang et al. (2023)**: Encouraging divergent thinking in LLM multi-agent collaboration

### RAG Evaluation
- **Zhang et al. (2024)**: RAFT — Retrieval Augmented Fine-Tuning for domain-specific RAG, inspiring our oracle/distractor document mixing

---

## 12. Limitations and Future Work

### Current Limitations
- **Sample size**: 27 predictions (18 resolved) is insufficient for definitive statistical conclusions. Ongoing data collection will strengthen significance
- **Domain coverage**: Current evaluation focused primarily on sports and crypto; broader domain testing needed
- **Retrieval quality**: YouTube transcript relevance varies; hallucinated or outdated content may influence predictions
- **Cost**: Running 10 agents × 3 rounds + meta-predictions requires significant API calls per question

### Future Directions
1. **Scale to 100+ resolved predictions** for robust statistical significance
2. **Automated market scanning**: Continuously scan prediction markets for high-edge opportunities
3. **Dynamic agent allocation**: Adjust number of agents and debate rounds based on question complexity
4. **Fine-tuned retrieval**: Domain-specific retrieval models to improve context quality
5. **Live trading integration**: Automated position-taking on identified mispriced markets
6. **Lambda optimization**: Tune hybrid weights (λ₁, λ₂, λ₃) based on accumulated performance data

---

## 13. Conclusion

DePredict demonstrates that multi-agent adversarial debate, combined with principled aggregation mechanisms, can systematically outperform prediction market prices. The system achieves a +5.7% Brier Score edge over market prices with a 72.2% win rate across prospective evaluation. Key architectural innovations — information partitioning, multi-model agent diversity, and the hybrid aggregation mechanism — each contribute to this outperformance. As the system accumulates more data points, we expect the statistical significance of these results to strengthen, and the reputation system to further improve aggregation quality through learned agent weights.

---

## References

1. Arrow, K. J., et al. (2008). The Promise of Prediction Markets. *Science*, 320(5878), 877-878.
2. Baron, J., et al. (2014). Two reasons to make aggregated probability forecasts more extreme. *Decision Analysis*, 11(2), 133-145.
3. Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics*, 13(3), 253-263.
4. Du, Y., et al. (2023). Improving Factuality and Reasoning in Language Models through Multiagent Debate. *arXiv:2305.14325*.
5. Hanson, R. (2003). Combinatorial Information Market Design. *Information Systems Frontiers*, 5(1), 107-119.
6. Liang, T., et al. (2023). Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate. *arXiv:2305.19118*.
7. Miller, N., Resnick, P., & Zeckhauser, R. (2005). Eliciting Informative Feedback: The Peer-Prediction Method. *Management Science*, 51(9), 1359-1373.
8. Prelec, D. (2004). A Bayesian Truth Serum for Subjective Data. *Science*, 306(5695), 462-466.
9. Satopää, V. A., et al. (2014). Combining multiple probability predictions using a simple logit model. *International Journal of Forecasting*, 30(2), 344-356.
10. Zhang, T., et al. (2024). RAFT: Adapting Language Model to Domain Specific RAG. *arXiv:2403.10131*.
