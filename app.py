"""
Streamlit dashboard for Prediction Market Debater.

Displays AI clone debate process and comparison with market prices.

Usage:
    streamlit run app.py
"""

import hashlib
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import RESULTS_DIR
from debate import DebatePipeline

st.set_page_config(
    page_title="AI Clone 辩论预测市场",
    page_icon="🎯",
    layout="wide",
)

# ── Styling ──────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .agent-card {
        background-color: #1e1e2e;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .bull { border-left-color: #4caf50; }
    .bear { border-left-color: #f44336; }
    .neutral { border-left-color: #2196f3; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────

st.title("AI Clone 辩论驱动预测市场")
st.caption("多个 AI 分析师针对预测问题进行 3 轮辩论")

# ── Sidebar: 输入问题 ────────────────────────────────────────────────────────

with st.sidebar:
    st.header("输入预测问题")

    user_question = st.text_area(
        "问题",
        placeholder="例：2025 NBA 总决赛冠军是否为波士顿凯尔特人？",
        height=100,
    )

    market_price_pct = st.number_input(
        "市场价格 %（可选，用于对比）",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=1.0,
        help="填 0 表示无市场价格对比",
    )

    market_price = market_price_pct / 100.0 if market_price_pct > 0 else None

    st.divider()
    st.caption("Powered by DeepSeek + Tavily + Streamlit")

if not user_question.strip():
    st.info("请在左侧输入一个预测问题，然后点击 **运行辩论**。")
    st.stop()

# ── Main Content ─────────────────────────────────────────────────────────────

st.markdown(f"**问题:** {user_question}")
if market_price is not None:
    st.markdown(f"**市场参考价格:** {market_price_pct:.1f}%")

st.divider()

# ── Load / Run Debate ────────────────────────────────────────────────────────


def _question_id(question: str) -> str:
    return hashlib.md5(question.encode()).hexdigest()[:12]


def get_result_path(question_id: str) -> str:
    return os.path.join(RESULTS_DIR, f"{question_id}.json")


def load_result(question_id: str) -> dict | None:
    path = get_result_path(question_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_result(question_id: str, result: dict):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(get_result_path(question_id), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


q_id = _question_id(user_question.strip())
result = load_result(q_id)

if st.button("运行辩论", type="primary", use_container_width=True):
    with st.spinner("10 位 AI 分析师正在辩论..."):
        pipeline = DebatePipeline()
        result = pipeline.run(user_question.strip(), market_price)
        save_result(q_id, result)
    st.rerun()

if result is None:
    st.info(
        "点击 **运行辩论** 开始。\n\n"
        "请确保在 `.env` 中设置了 `DEEPSEEK_API_KEY` 和 `TAVILY_API_KEY`。"
    )
    st.stop()

# ── RAFT Metrics ─────────────────────────────────────────────────────────────

raft_metrics = result.get("raft_metrics", {})
if raft_metrics:
    st.header("RAFT 指标")
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        acc = raft_metrics.get("citation_accuracy", 0)
        st.metric("引用准确率", f"{acc:.1%}")
    with mcol2:
        rej = raft_metrics.get("distractor_rejection_rate", 0)
        st.metric("干扰拒绝率", f"{rej:.1%}")
    with mcol3:
        st.metric("总引用数", raft_metrics.get("total_citations", 0))
    with mcol4:
        oracle_cited = raft_metrics.get("oracle_docs_cited", 0)
        dist_cited = raft_metrics.get("distractor_docs_cited", 0)
        st.metric("引用文档", f"{oracle_cited} oracle / {dist_cited} distractor")

    st.caption(
        f"混合文档总数: {result.get('mixed_docs_count', 'N/A')} | "
        f"Oracle 文档: {result.get('oracle_count', 'N/A')} | "
        f"干扰文档: {result.get('distractor_count', 'N/A')}"
    )
    st.divider()

# ── RAG Sources ──────────────────────────────────────────────────────────────

with st.expander("查看检索到的信息来源 (Oracle 文档)"):
    for src in result.get("rag_sources", []):
        st.markdown(f"**{src['title']}** (相关度: {src.get('score', 'N/A')})")
        st.markdown(f"{src['content'][:300]}...")
        st.markdown(f"[链接]({src['url']})")
        st.markdown("---")

# ── Debate Rounds ────────────────────────────────────────────────────────────

st.header("辩论过程")

rounds = result.get("rounds", {})
tab1, tab2, tab3, tab4 = st.tabs([
    "Round 1: 独立预测", "Round 2: 交叉反驳", "Round 3: 最终预测", "预测变化"
])

stance_colors = {"bull": "#4caf50", "bear": "#f44336", "neutral": "#2196f3"}
stance_labels = {"bull": "看多", "bear": "看空", "neutral": "中立"}

def _render_citations(citations_data):
    """Render citation quotes in a compact format."""
    if not citations_data:
        return
    quotes = citations_data.get("quotes", []) if isinstance(citations_data, dict) else []
    if quotes:
        with st.expander(f"引用来源 ({len(quotes)} 条)"):
            for q in quotes:
                st.markdown(f"> {q['quote']}  \n> — *[文档 {q['doc_index']}]*")


with tab1:
    for r1 in rounds.get("round1", []):
        color = stance_colors.get(r1.get("stance", ""), "#888")
        label = stance_labels.get(r1.get("stance", ""), r1.get("stance", ""))
        prob_str = f"{r1['probability']}%" if r1["probability"] is not None else "N/A"

        st.markdown(f"#### {r1['agent_name']} ({label})")
        st.markdown(f"**预测:** {prob_str}")
        st.markdown(f"**推理:** {r1.get('reasoning', 'N/A')}")
        _render_citations(r1.get("citations"))
        st.markdown("---")

with tab2:
    for r2 in rounds.get("round2", []):
        label = stance_labels.get(r2.get("stance", ""), r2.get("stance", ""))
        prob_str = f"{r2['probability']}%" if r2["probability"] is not None else "N/A"

        st.markdown(f"#### {r2['agent_name']} ({label})")
        if r2.get("rebuttals"):
            st.markdown(f"**反驳:**\n\n{r2['rebuttals']}")
        st.markdown(f"**修正推理:** {r2.get('reasoning', 'N/A')}")
        st.markdown(f"**修正预测:** {prob_str}")
        _render_citations(r2.get("citations"))
        st.markdown("---")

with tab3:
    for r3 in rounds.get("round3", []):
        label = stance_labels.get(r3.get("stance", ""), r3.get("stance", ""))
        prob_str = f"{r3['probability']}%" if r3["probability"] is not None else "N/A"

        st.markdown(f"#### {r3['agent_name']} ({label})")
        st.markdown(f"**最终推理:** {r3.get('reasoning', 'N/A')}")
        st.markdown(f"**最终预测:** {prob_str}")
        _render_citations(r3.get("citations"))
        st.markdown("---")

with tab4:
    st.markdown("**各分析师预测在辩论中的变化：**")

    r1_by_name = {r["agent_name"]: r for r in rounds.get("round1", [])}
    r2_by_name = {r["agent_name"]: r for r in rounds.get("round2", [])}
    r3_by_name = {r["agent_name"]: r for r in rounds.get("round3", [])}

    shift_data = []
    for name in r1_by_name:
        r1_p = r1_by_name[name].get("probability")
        r2_p = r2_by_name.get(name, {}).get("probability")
        r3_p = r3_by_name.get(name, {}).get("probability")

        row = {"分析师": name}
        row["Round 1"] = f"{r1_p}%" if r1_p is not None else "N/A"
        row["Round 2"] = f"{r2_p}%" if r2_p is not None else "N/A"
        row["Round 3"] = f"{r3_p}%" if r3_p is not None else "N/A"

        if r1_p is not None and r3_p is not None:
            diff = r3_p - r1_p
            row["变化"] = f"{diff:+.1f}%"
        else:
            row["变化"] = "N/A"

        shift_data.append(row)

    if shift_data:
        st.dataframe(pd.DataFrame(shift_data), hide_index=True, use_container_width=True)

# ── Aggregated vs Market ─────────────────────────────────────────────────────

st.divider()
st.header("预测对比")

agg_prob = result.get("aggregated_probability", 0) or 0
r1_avg = result.get("round1_average", 0) or 0
market_raw = result.get("market_price")
market = market_raw * 100 if market_raw else None

fig = go.Figure()

fig.add_trace(go.Bar(
    name="Round 1 平均 (无辩论)",
    x=["预测概率"],
    y=[r1_avg],
    marker_color="#9e9e9e",
    text=[f"{r1_avg:.1f}%"],
    textposition="outside",
))

fig.add_trace(go.Bar(
    name="Round 3 平均 (有辩论)",
    x=["预测概率"],
    y=[agg_prob],
    marker_color="#6366f1",
    text=[f"{agg_prob:.1f}%"],
    textposition="outside",
))

if market is not None:
    fig.add_trace(go.Bar(
        name="市场价格",
        x=["预测概率"],
        y=[market],
        marker_color="#f59e0b",
        text=[f"{market:.1f}%"],
        textposition="outside",
    ))

# Add individual agent traces
agent_colors = [
    "#4caf50", "#f44336", "#2196f3", "#ff9800", "#9c27b0",
    "#00bcd4", "#e91e63", "#8bc34a", "#795548", "#607d8b",
]
for i, agent_info in enumerate(result.get("agents", [])):
    final = agent_info.get("final", {})
    prob = final.get("probability", 0) or 0
    fig.add_trace(go.Scatter(
        name=agent_info["name"],
        x=["预测概率"],
        y=[prob],
        mode="markers",
        marker=dict(
            color=agent_colors[i % len(agent_colors)],
            size=14,
            symbol="diamond",
        ),
    ))

fig.update_layout(
    barmode="group",
    yaxis_title="概率 (%)",
    yaxis_range=[0, 105],
    height=400,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=60),
)

st.plotly_chart(fig, use_container_width=True)

# ── Summary Table ────────────────────────────────────────────────────────────

st.subheader("详细对比")

summary_data = []
for agent_info in result.get("agents", []):
    final = agent_info.get("final", {})
    prob = final.get("probability")
    prob_str = f"{prob}%" if prob is not None else "N/A"
    summary_data.append({
        "分析师": agent_info["name"],
        "立场": stance_labels.get(agent_info["stance"], agent_info["stance"]),
        "最终预测": prob_str,
    })

summary_data.append({
    "分析师": "聚合平均",
    "立场": "-",
    "最终预测": f"{agg_prob:.1f}%",
})

if market is not None:
    summary_data.append({
        "分析师": "市场价格",
        "立场": "市场",
        "最终预测": f"{market:.1f}%",
    })
    diff = agg_prob - market
    summary_data.append({
        "分析师": "差异 (AI - 市场)",
        "立场": "-",
        "最终预测": f"{diff:+.1f}%",
    })

st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)

# ── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"上次运行: {result.get('timestamp', 'unknown')} | "
    f"Agent 数量: {len(result.get('agents', []))} | "
    f"辩论轮数: 3"
)
