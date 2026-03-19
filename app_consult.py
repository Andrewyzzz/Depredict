"""
Streamlit app for AI Expert Consultation platform.

Users bring their own opinions, debate with AI domain experts,
and arrive at refined conclusions.

Usage:
    streamlit run app_consult.py
"""

import hashlib
import json
import os

import streamlit as st

from config import RESULTS_DIR
from consultation import ConsultationPipeline, save_consultation
from expert_panels import DOMAIN_PANELS

st.set_page_config(
    page_title="AI Expert Consultation",
    page_icon="🧠",
    layout="wide",
)

# ── Styling ──────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .expert-card {
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        border-left: 4px solid;
    }
    .stance-supportive { border-left-color: #4caf50; background-color: #1a2e1a; }
    .stance-skeptical { border-left-color: #f44336; background-color: #2e1a1a; }
    .stance-cautious { border-left-color: #ff9800; background-color: #2e2a1a; }
    .stance-neutral { border-left-color: #2196f3; background-color: #1a1a2e; }
    .report-box {
        background-color: #1e1e2e;
        border-radius: 12px;
        padding: 24px;
        margin: 16px 0;
    }
    .phase-header {
        font-size: 1.2em;
        font-weight: bold;
        margin: 16px 0 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Session State Init ───────────────────────────────────────────────────────

if "consultation_result" not in st.session_state:
    st.session_state.consultation_result = None
if "current_phase" not in st.session_state:
    st.session_state.current_phase = "input"
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = {}  # {expert_name: [messages]}
if "pipeline" not in st.session_state:
    st.session_state.pipeline = None
if "context_text" not in st.session_state:
    st.session_state.context_text = ""
if "topic" not in st.session_state:
    st.session_state.topic = ""
if "user_opinion" not in st.session_state:
    st.session_state.user_opinion = ""

# ── Header ───────────────────────────────────────────────────────────────────

st.title("AI Expert Consultation")
st.caption("Bring your opinion. Challenge the experts. Refine your thinking.")

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Start a Consultation")

    domain = st.selectbox(
        "Select Domain",
        options=list(DOMAIN_PANELS.keys()),
        format_func=lambda x: f"{DOMAIN_PANELS[x]['label']} - {DOMAIN_PANELS[x]['description'][:20]}...",
    )

    panel_info = DOMAIN_PANELS[domain]

    st.markdown(f"**{panel_info['label']}**")
    st.markdown(f"{panel_info['description']}")

    st.markdown("**Expert Panel:**")
    for expert in panel_info["experts"]:
        stance_emoji = {"supportive": "🟢", "skeptical": "🔴", "cautious": "🟡", "neutral": "🔵"}.get(expert["stance"], "⚪")
        st.markdown(f"{stance_emoji} **{expert['name']}** ({expert['role']})")

    st.divider()

    st.markdown("**Example Topics:**")
    for example in panel_info["example_topics"]:
        st.markdown(f"- {example}")

    st.divider()
    st.caption("Powered by DeepSeek + Multi-LLM")

# ── Main Content ─────────────────────────────────────────────────────────────

# Input Phase
if st.session_state.current_phase == "input":
    st.header("What's on your mind?")

    col1, col2 = st.columns([1, 1])

    with col1:
        topic = st.text_input(
            "Topic / Question",
            placeholder="e.g., 比特币今年能到15万美元吗？",
            key="topic_input",
        )

    with col2:
        st.markdown("")  # spacer

    user_opinion = st.text_area(
        "Your Opinion & Reasoning",
        placeholder="Share your view and why you think this way...\n\ne.g., 我认为比特币今年能到15万美元，因为：\n1. ETF资金持续流入\n2. 减半效应还没完全体现\n3. 全球流动性在增加",
        height=200,
        key="opinion_input",
    )

    if st.button("Consult Experts", type="primary", use_container_width=True):
        if not topic.strip() or not user_opinion.strip():
            st.warning("Please provide both a topic and your opinion.")
        else:
            st.session_state.topic = topic.strip()
            st.session_state.user_opinion = user_opinion.strip()
            st.session_state.current_phase = "running_phase1"
            st.rerun()

# Running Phase 1
elif st.session_state.current_phase == "running_phase1":
    st.header(f"Consulting experts on: {st.session_state.topic}")
    st.info(f"**Your opinion:** {st.session_state.user_opinion}")

    with st.spinner("Retrieving background information and consulting experts..."):
        pipeline = ConsultationPipeline(domain)
        st.session_state.pipeline = pipeline

        # Retrieve context
        rag_result = pipeline.retrieve_context(st.session_state.topic)
        st.session_state.context_text = rag_result["context_text"]
        st.session_state.rag_sources = rag_result["relevant"]

        # Phase 1: Expert evaluations
        evaluations = pipeline.phase1_evaluate(
            st.session_state.topic,
            st.session_state.user_opinion,
            st.session_state.context_text,
        )
        st.session_state.evaluations = evaluations

        # Initialize chat for each expert
        for ev in evaluations:
            st.session_state.chat_messages[ev["agent_name"]] = []

    st.session_state.current_phase = "phase2"
    st.rerun()

# Phase 2: Interactive - User reads evaluations and can chat
elif st.session_state.current_phase == "phase2":
    st.header(f"Expert Evaluations: {st.session_state.topic}")

    # Show user's opinion
    with st.expander("Your Opinion", expanded=False):
        st.markdown(st.session_state.user_opinion)

    # Show RAG sources
    with st.expander("Background Sources", expanded=False):
        for src in st.session_state.get("rag_sources", []):
            st.markdown(f"**{src['title']}**")
            st.markdown(f"{src['content'][:200]}...")
            st.markdown("---")

    st.divider()

    # Expert evaluations in tabs
    evaluations = st.session_state.evaluations
    expert_names = [ev["agent_name"] for ev in evaluations]

    tabs = st.tabs([f"{ev['agent_name']}" for ev in evaluations])

    for tab, ev in zip(tabs, evaluations):
        with tab:
            stance_class = f"stance-{ev.get('stance', 'neutral')}"
            conf = ev.get("confidence", "N/A")

            st.markdown(f"**{ev['agent_name']}** ({ev.get('role', '')}) | Confidence: {conf}%")

            # Assessment
            st.markdown(f"**Overall:** {ev.get('assessment', 'N/A')}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Agree:**")
                st.markdown(ev.get("agree_points", "N/A"))
            with col2:
                st.markdown("**Challenge:**")
                st.markdown(ev.get("challenge_points", "N/A"))

            st.markdown(f"**Key Insight:** {ev.get('key_insight', 'N/A')}")

            # Chat with this expert
            st.divider()
            st.markdown(f"**Chat with {ev['agent_name']}**")

            chat_key = ev["agent_name"]
            messages = st.session_state.chat_messages.get(chat_key, [])

            # Display chat history
            for msg in messages:
                role = "user" if msg["role"] == "user" else "assistant"
                with st.chat_message(role, avatar="🧑" if role == "user" else "🎓"):
                    st.markdown(msg["content"])

            # Chat input
            user_msg = st.chat_input(
                f"Ask {ev['agent_name']} a question...",
                key=f"chat_{chat_key}",
            )

            if user_msg:
                # Add user message
                st.session_state.chat_messages[chat_key].append(
                    {"role": "user", "content": user_msg}
                )

                # Get expert response
                pipeline = st.session_state.pipeline
                agent = next(a for a in pipeline.agents if a.name == chat_key)

                with st.spinner(f"{chat_key} is thinking..."):
                    response = agent.respond_to_user(
                        st.session_state.topic,
                        st.session_state.user_opinion,
                        user_msg,
                        st.session_state.context_text,
                    )

                st.session_state.chat_messages[chat_key].append(
                    {"role": "expert", "content": response}
                )
                st.rerun()

    # Continue to Phase 3
    st.divider()
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(
            "Continue to Expert Discussion & Final Report",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.current_phase = "running_phase34"
            st.rerun()

# Running Phases 3 & 4
elif st.session_state.current_phase == "running_phase34":
    st.header("Experts are discussing among themselves...")

    pipeline = st.session_state.pipeline

    with st.spinner("Phase 3: Expert round-table discussion..."):
        discussions = pipeline.phase3_discuss(
            st.session_state.topic,
            st.session_state.user_opinion,
            st.session_state.evaluations,
            st.session_state.context_text,
        )
        st.session_state.discussions = discussions

    with st.spinner("Phase 4: Generating final assessments..."):
        finals = pipeline.phase4_final(
            st.session_state.topic,
            st.session_state.user_opinion,
            discussions,
            st.session_state.context_text,
        )
        st.session_state.finals = finals

    # Build and save full result
    result = {
        "topic": st.session_state.topic,
        "user_opinion": st.session_state.user_opinion,
        "domain": domain,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "rag_sources": st.session_state.get("rag_sources", []),
        "phases": {
            "evaluations": st.session_state.evaluations,
            "discussions": discussions,
            "finals": finals,
        },
        "chat_logs": {
            name: msgs
            for name, msgs in st.session_state.chat_messages.items()
            if msgs  # only save non-empty chats
        },
        "experts": [
            {"name": a.name, "role": a.role, "stance": a.stance}
            for a in pipeline.agents
        ],
    }
    st.session_state.consultation_result = result

    # Save to disk
    save_consultation(result)

    st.session_state.current_phase = "report"
    st.rerun()

# Final Report
elif st.session_state.current_phase == "report":
    result = st.session_state.consultation_result
    evaluations = result["phases"]["evaluations"]
    discussions = result["phases"]["discussions"]
    finals = result["phases"]["finals"]

    st.header(f"Consultation Report: {result['topic']}")

    # User opinion reminder
    with st.expander("Your Original Opinion", expanded=False):
        st.markdown(result["user_opinion"])

    st.divider()

    # ── Expert Final Assessments ─────────────────────────────────────────
    st.subheader("Expert Final Assessments")

    for f in finals:
        stance_emoji = {
            "supportive": "🟢", "skeptical": "🔴",
            "cautious": "🟡", "neutral": "🔵",
        }.get(f.get("stance", ""), "⚪")

        with st.container():
            st.markdown(f"### {stance_emoji} {f['agent_name']} ({f.get('role', '')})")

            conf = f.get("confidence", "N/A")
            st.markdown(f"**Confidence:** {conf}%")
            st.markdown(f"**Assessment:** {f.get('final_assessment', 'N/A')}")
            st.markdown(f"**Recommendation:** {f.get('recommendation', 'N/A')}")
            st.markdown(f"**Risk Warning:** {f.get('risk_warning', 'N/A')}")
            st.divider()

    # ── Confidence Overview ──────────────────────────────────────────────
    st.subheader("Expert Confidence Overview")

    import plotly.graph_objects as go

    expert_names = [f["agent_name"] for f in finals]
    eval_confs = []
    final_confs = []
    for ev, fn in zip(evaluations, finals):
        eval_confs.append(ev.get("confidence") or 0)
        final_confs.append(fn.get("confidence") or 0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Phase 1 (Initial)",
        x=expert_names,
        y=eval_confs,
        marker_color="#6366f1",
        text=[f"{c:.0f}%" for c in eval_confs],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Phase 4 (Final)",
        x=expert_names,
        y=final_confs,
        marker_color="#22c55e",
        text=[f"{c:.0f}%" for c in final_confs],
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        yaxis_title="Confidence (%)",
        yaxis_range=[0, 110],
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Discussion Details ───────────────────────────────────────────────
    with st.expander("Expert Discussion Details (Phase 3)", expanded=False):
        for d in discussions:
            st.markdown(f"**{d['agent_name']}** ({d.get('role', '')})")
            st.markdown(f"**Responses:** {d.get('responses', 'N/A')}")
            st.markdown(f"**Updated Assessment:** {d.get('updated_assessment', 'N/A')}")
            st.markdown(f"**Blind Spots:** {d.get('blind_spots', 'N/A')}")
            st.markdown("---")

    # ── Chat Logs ────────────────────────────────────────────────────────
    chat_logs = result.get("chat_logs", {})
    if chat_logs:
        with st.expander("Your Conversations with Experts", expanded=False):
            for expert_name, messages in chat_logs.items():
                st.markdown(f"### {expert_name}")
                for msg in messages:
                    role_label = "You" if msg["role"] == "user" else expert_name
                    st.markdown(f"**{role_label}:** {msg['content']}")
                st.markdown("---")

    # ── Synthesized Insights ─────────────────────────────────────────────
    st.divider()
    st.subheader("Key Takeaways")

    # Collect all insights and challenges
    all_insights = [ev.get("key_insight", "") for ev in evaluations if ev.get("key_insight")]
    all_blind_spots = [d.get("blind_spots", "") for d in discussions if d.get("blind_spots")]
    all_recommendations = [f.get("recommendation", "") for f in finals if f.get("recommendation")]
    all_risks = [f.get("risk_warning", "") for f in finals if f.get("risk_warning")]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Key Insights:**")
        for i, insight in enumerate(all_insights, 1):
            st.markdown(f"{i}. {insight}")

        st.markdown("**Blind Spots:**")
        for bs in all_blind_spots:
            if bs:
                st.markdown(f"- {bs}")

    with col2:
        st.markdown("**Recommendations:**")
        for rec in all_recommendations:
            if rec:
                st.markdown(f"- {rec}")

        st.markdown("**Risk Warnings:**")
        for rw in all_risks:
            if rw:
                st.markdown(f"- {rw}")

    # ── Start Over ───────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Start New Consultation", use_container_width=True):
            st.session_state.current_phase = "input"
            st.session_state.consultation_result = None
            st.session_state.chat_messages = {}
            st.session_state.pipeline = None
            st.rerun()

# ── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Phase: {st.session_state.current_phase} | "
    f"Domain: {DOMAIN_PANELS.get(domain, {}).get('label', domain)}"
)
