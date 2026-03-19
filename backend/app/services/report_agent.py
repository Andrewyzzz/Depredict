"""
ReACT-style report agent for generating structured prediction reports.

Inspired by MiroFish's ReportAgent. Generates comprehensive analysis reports
after a debate completes, using tool-augmented reasoning loops.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI

# Add project root to path for config access
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DATA_DIR,
)


class ReportAgent:
    """
    ReACT-style agent that generates structured prediction reports.

    Uses a set of analytical tools in a reasoning loop to gather information
    from debate results, then assembles a comprehensive markdown report.
    """

    TOOL_DESCRIPTIONS = """Available tools:
1. analyze_debate(query: str) - Analyze debate history. Example queries: "who changed stance?", "largest disagreements", "consensus points"
2. compare_market(question: str) - Compare model probability vs market price, compute edge
3. check_calibration(category: str) - Check historical accuracy for similar question categories
4. extract_arguments(side: str) - Extract top 3 arguments for a given side ("bull" or "bear")

To use a tool, write: TOOL: tool_name(argument)
After receiving observations, continue reasoning or write SECTION_CONTENT: to output the section."""

    def __init__(self, task_state):
        """
        Initialize with a completed debate task state.

        Args:
            task_state: DebateTaskState with status=COMPLETED and result populated.
        """
        self.task_state = task_state
        self.result = task_state.result or {}
        self.question = self.result.get("question", task_state.question)
        self.market_price = self.result.get("market_price", task_state.market_price)

        # Initialize OpenAI client (using DeepSeek for cost efficiency)
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self.model = DEEPSEEK_MODEL

    def generate_report(self) -> str:
        """
        Generate a full markdown prediction report.

        Steps:
            1. Plan outline (2-5 sections)
            2. For each section, run ReACT loop (max 5 iterations, min 3 tool calls)
            3. Assemble sections into final markdown

        Returns:
            Complete markdown report string.
        """
        # Step 1: Plan outline
        sections = self._plan_outline()

        # Step 2: Generate each section via ReACT loop
        section_contents = []
        for section in sections:
            content = self._react_loop(section["title"], section["prompt"])
            section_contents.append({
                "title": section["title"],
                "content": content,
            })

        # Step 3: Assemble
        return self._assemble_report(section_contents)

    def _plan_outline(self) -> list[dict]:
        """Plan the report outline using LLM."""
        agg = self.result.get("aggregation_mechanisms", {})
        hybrid_prob = agg.get("hybrid", {}).get("probability")
        simple_avg = agg.get("simple_average", {}).get("probability")
        best_prob = hybrid_prob or simple_avg

        market_str = f"{self.market_price * 100:.1f}%" if self.market_price else "N/A"
        model_str = f"{best_prob:.1f}%" if best_prob else "N/A"

        prompt = f"""You are planning a prediction analysis report for the question:
"{self.question}"

Model probability: {model_str}
Market price: {market_str}
Number of debate agents: {len(self.result.get('agents', []))}
Debate rounds: 3

Plan 4-5 sections for the report. Output JSON array:
[{{"title": "section title in Chinese", "prompt": "what this section should cover"}}]

Required sections:
1. Core conclusion with probability comparison
2. Multi-expert debate summary
3. Aggregation mechanism analysis
4. Risk warnings

Optional: historical calibration reference, key arguments breakdown.

Output ONLY the JSON array, no other text."""

        response = self._llm_call(prompt)
        try:
            sections = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                try:
                    sections = json.loads(match.group())
                except json.JSONDecodeError:
                    sections = self._default_sections()
            else:
                sections = self._default_sections()

        return sections

    def _default_sections(self) -> list[dict]:
        """Fallback section plan."""
        return [
            {"title": "核心结论", "prompt": "Present the core conclusion with model probability vs market price"},
            {"title": "多专家辩论摘要", "prompt": "Summarize the multi-agent debate across 3 rounds"},
            {"title": "聚合机制分析", "prompt": "Compare different aggregation mechanisms and their outputs"},
            {"title": "历史校准参考", "prompt": "Reference historical calibration performance"},
            {"title": "风险提示", "prompt": "Identify key risks and caveats"},
        ]

    def _react_loop(self, section_title: str, section_prompt: str) -> str:
        """
        Run a ReACT reasoning loop for a single report section.

        Args:
            section_title: Title of the section being generated.
            section_prompt: Description of what the section should cover.

        Returns:
            Generated section content (markdown).
        """
        system_msg = f"""You are a prediction market analyst writing a section of a report.

Section: {section_title}
Goal: {section_prompt}
Question: {self.question}

{self.TOOL_DESCRIPTIONS}

You MUST call at least 3 tools before writing the section content.
After gathering enough information, write the section content prefixed with SECTION_CONTENT:

Think step by step:
1. What information do I need for this section?
2. Call relevant tools to gather data
3. Analyze the observations
4. Write the section content in Chinese (markdown format)"""

        messages = [{"role": "system", "content": system_msg}]
        messages.append({"role": "user", "content": f"Generate the '{section_title}' section. Start by calling tools to gather information."})

        tool_calls_made = 0
        max_iterations = 5
        min_tool_calls = 3

        for iteration in range(max_iterations):
            response = self._llm_call_messages(messages)
            messages.append({"role": "assistant", "content": response})

            # Check if section content is ready
            if "SECTION_CONTENT:" in response and tool_calls_made >= min_tool_calls:
                content = response.split("SECTION_CONTENT:", 1)[1].strip()
                return content

            # Parse and execute tool calls
            tool_results = []
            for match in re.finditer(r'TOOL:\s*(\w+)\(([^)]*)\)', response):
                tool_name = match.group(1)
                tool_arg = match.group(2).strip().strip('"').strip("'")
                result = self._execute_tool(tool_name, tool_arg)
                tool_results.append(f"[{tool_name}] Observation: {result}")
                tool_calls_made += 1

            if tool_results:
                observation = "\n\n".join(tool_results)
                messages.append({"role": "user", "content": f"Observations:\n{observation}\n\nContinue reasoning. {'You have made enough tool calls, you can now write SECTION_CONTENT:' if tool_calls_made >= min_tool_calls else 'Call more tools to gather information.'}"})
            else:
                # No tool calls found, prompt to either use tools or write content
                if tool_calls_made >= min_tool_calls:
                    messages.append({"role": "user", "content": "You have gathered enough information. Please write SECTION_CONTENT: followed by the section content in Chinese markdown."})
                else:
                    messages.append({"role": "user", "content": f"Please call tools using TOOL: tool_name(argument) format. You need at least {min_tool_calls - tool_calls_made} more tool calls."})

        # If we exhausted iterations, try to extract any content
        last_response = messages[-1]["content"] if messages else ""
        if "SECTION_CONTENT:" in last_response:
            return last_response.split("SECTION_CONTENT:", 1)[1].strip()

        # Final fallback: ask for content directly
        messages.append({"role": "user", "content": "Time is up. Please write SECTION_CONTENT: followed by the section content now."})
        response = self._llm_call_messages(messages)
        if "SECTION_CONTENT:" in response:
            return response.split("SECTION_CONTENT:", 1)[1].strip()
        return response

    def _execute_tool(self, tool_name: str, argument: str) -> str:
        """Execute a tool and return its observation as a string."""
        tools = {
            "analyze_debate": self._tool_analyze_debate,
            "compare_market": self._tool_compare_market,
            "check_calibration": self._tool_check_calibration,
            "extract_arguments": self._tool_extract_arguments,
        }

        tool_fn = tools.get(tool_name)
        if tool_fn is None:
            return f"Error: Unknown tool '{tool_name}'. Available: {list(tools.keys())}"

        try:
            return tool_fn(argument)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def _tool_analyze_debate(self, query: str) -> str:
        """
        Analyze debate history based on a query.

        Searches through round1/2/3 results for patterns matching the query.
        """
        rounds = self.result.get("rounds", {})
        round1 = rounds.get("round1", [])
        round2 = rounds.get("round2", [])
        round3 = rounds.get("round3", [])

        analysis_parts = []

        # Track probability changes across rounds
        agent_trajectories = {}
        for r1 in round1:
            name = r1.get("agent_name", "")
            agent_trajectories[name] = {
                "stance": r1.get("stance", ""),
                "round1": r1.get("probability"),
                "round2": None,
                "round3": None,
            }

        for r2 in round2:
            name = r2.get("agent_name", "")
            if name in agent_trajectories:
                agent_trajectories[name]["round2"] = r2.get("probability")

        for r3 in round3:
            name = r3.get("agent_name", "")
            if name in agent_trajectories:
                agent_trajectories[name]["round3"] = r3.get("probability")

        query_lower = query.lower()

        if "change" in query_lower or "stance" in query_lower or "shift" in query_lower:
            # Who changed stance the most?
            changes = []
            for name, traj in agent_trajectories.items():
                r1p = traj["round1"]
                r3p = traj["round3"]
                if r1p is not None and r3p is not None:
                    delta = r3p - r1p
                    changes.append((name, traj["stance"], r1p, r3p, delta))
            changes.sort(key=lambda x: abs(x[4]), reverse=True)
            analysis_parts.append("Agents sorted by magnitude of probability change (R1 -> R3):")
            for name, stance, r1p, r3p, delta in changes[:5]:
                direction = "increased" if delta > 0 else "decreased"
                analysis_parts.append(f"  {name} ({stance}): {r1p}% -> {r3p}% ({direction} by {abs(delta):.1f}pp)")

        elif "disagree" in query_lower or "diverge" in query_lower:
            # Largest disagreements in round 3
            r3_probs = [(r.get("agent_name", ""), r.get("probability")) for r in round3 if r.get("probability") is not None]
            if r3_probs:
                probs = [p for _, p in r3_probs]
                spread = max(probs) - min(probs)
                highest = max(r3_probs, key=lambda x: x[1])
                lowest = min(r3_probs, key=lambda x: x[1])
                analysis_parts.append(f"Round 3 spread: {spread:.1f}pp")
                analysis_parts.append(f"Highest: {highest[0]} at {highest[1]}%")
                analysis_parts.append(f"Lowest: {lowest[0]} at {lowest[1]}%")

        elif "consensus" in query_lower:
            # Points of consensus
            r3_probs = [r.get("probability") for r in round3 if r.get("probability") is not None]
            if r3_probs:
                import statistics
                avg = statistics.mean(r3_probs)
                std = statistics.stdev(r3_probs) if len(r3_probs) > 1 else 0
                analysis_parts.append(f"Round 3 average: {avg:.1f}%, std: {std:.1f}")
                analysis_parts.append(f"Consensus level: {'high' if std < 10 else 'moderate' if std < 20 else 'low'}")
        else:
            # General summary
            r3_probs = [r.get("probability") for r in round3 if r.get("probability") is not None]
            if r3_probs:
                import statistics
                analysis_parts.append(f"Round 3: {len(round3)} agents, avg={statistics.mean(r3_probs):.1f}%")
                analysis_parts.append(f"Min={min(r3_probs)}%, Max={max(r3_probs)}%")

            # Show all trajectories
            for name, traj in list(agent_trajectories.items())[:5]:
                analysis_parts.append(
                    f"  {name} ({traj['stance']}): R1={traj['round1']}% R2={traj['round2']}% R3={traj['round3']}%"
                )

        return "\n".join(analysis_parts) if analysis_parts else "No relevant debate data found."

    def _tool_compare_market(self, question: str) -> str:
        """Compare model probability vs market price."""
        agg = self.result.get("aggregation_mechanisms", {})
        market_price = self.market_price

        lines = [f"Question: {self.question}"]

        if market_price is not None:
            lines.append(f"Market price: {market_price * 100:.1f}%")
        else:
            lines.append("Market price: N/A")

        lines.append("\nModel probabilities by mechanism:")
        for method, info in agg.items():
            prob = info.get("probability")
            if prob is not None:
                edge_str = ""
                if market_price is not None:
                    edge = prob / 100.0 - market_price
                    edge_str = f" (edge: {edge * 100:+.1f}pp)"
                lines.append(f"  {method}: {prob:.1f}%{edge_str}")

        # Highlight largest edge
        if market_price is not None:
            hybrid_prob = agg.get("hybrid", {}).get("probability")
            if hybrid_prob:
                edge = hybrid_prob / 100.0 - market_price
                direction = "underpriced by market" if edge > 0 else "overpriced by market"
                lines.append(f"\nHybrid model edge: {abs(edge) * 100:.1f}pp ({direction})")

        return "\n".join(lines)

    def _tool_check_calibration(self, category: str) -> str:
        """Check historical calibration for a category."""
        questions_path = os.path.join(DATA_DIR, "questions.json")
        if not os.path.exists(questions_path):
            return "No historical calibration data available (questions.json not found)."

        with open(questions_path, "r", encoding="utf-8") as f:
            questions = json.load(f)

        # Filter resolved questions by category
        category_lower = category.lower()
        resolved = [
            q for q in questions
            if q.get("resolved") and q.get("resolution") is not None
            and (category_lower == "all" or q.get("category", "").lower() == category_lower)
        ]

        if not resolved:
            return f"No resolved questions found for category '{category}'."

        # Load results and compute Brier scores
        results_dir = os.path.join(DATA_DIR, "results")
        brier_scores = {"hybrid": [], "simple_average": [], "market": []}

        for q in resolved:
            result_path = os.path.join(results_dir, f"{q['id']}.json")
            if not os.path.exists(result_path):
                continue

            with open(result_path, "r", encoding="utf-8") as f:
                result = json.load(f)

            outcome = 1.0 if q["resolution"] else 0.0

            # Market Brier
            mp = q.get("market_price")
            if mp is not None:
                brier_scores["market"].append((mp - outcome) ** 2)

            # Mechanism Brier scores
            mechanisms = result.get("aggregation_mechanisms", {})
            for method in ["hybrid", "simple_average"]:
                prob = mechanisms.get(method, {}).get("probability")
                if prob is not None:
                    p = prob / 100.0
                    brier_scores[method].append((p - outcome) ** 2)

        lines = [f"Historical calibration for '{category}' ({len(resolved)} resolved questions):"]
        for method, scores in brier_scores.items():
            if scores:
                import statistics
                avg = statistics.mean(scores)
                lines.append(f"  {method}: Brier={avg:.4f} (n={len(scores)})")

        return "\n".join(lines)

    def _tool_extract_arguments(self, side: str) -> str:
        """Extract top 3 arguments for/against from debate rounds."""
        rounds = self.result.get("rounds", {})
        round3 = rounds.get("round3", [])

        # Filter agents by stance
        side_lower = side.lower()
        if side_lower in ("bull", "for", "yes"):
            target_stances = {"bull"}
            label = "FOR (bull)"
        elif side_lower in ("bear", "against", "no"):
            target_stances = {"bear"}
            label = "AGAINST (bear)"
        else:
            target_stances = {"neutral"}
            label = "NEUTRAL"

        # Collect reasoning from matching agents
        reasonings = []
        for r in round3:
            if r.get("stance") in target_stances:
                reasoning = r.get("reasoning", "")
                if reasoning:
                    reasonings.append({
                        "agent": r.get("agent_name", ""),
                        "probability": r.get("probability"),
                        "reasoning": reasoning[:500],  # Truncate for context window
                    })

        if not reasonings:
            # Fall back to all agents
            for r in round3:
                reasoning = r.get("reasoning", "")
                if reasoning:
                    reasonings.append({
                        "agent": r.get("agent_name", ""),
                        "probability": r.get("probability"),
                        "reasoning": reasoning[:500],
                    })

        lines = [f"Arguments from {label} perspective ({len(reasonings)} agents):"]
        for i, r in enumerate(reasonings[:3], 1):
            lines.append(f"\n{i}. {r['agent']} (prob: {r['probability']}%):")
            lines.append(f"   {r['reasoning'][:300]}...")

        return "\n".join(lines)

    def _assemble_report(self, sections: list[dict]) -> str:
        """Assemble sections into a full markdown report."""
        agg = self.result.get("aggregation_mechanisms", {})
        hybrid_prob = agg.get("hybrid", {}).get("probability")
        simple_avg = agg.get("simple_average", {}).get("probability")
        best_prob = hybrid_prob or simple_avg

        market_str = f"{self.market_price * 100:.1f}%" if self.market_price else "N/A"
        model_str = f"{best_prob:.1f}%" if best_prob else "N/A"

        if self.market_price and best_prob:
            edge = best_prob / 100.0 - self.market_price
            edge_str = f"{edge * 100:+.1f}%"
        else:
            edge_str = "N/A"

        # Header
        lines = [
            f"# 预测分析报告：{self.question}",
            "",
            f"> 模型概率: {model_str} | 市场价格: {market_str} | 错价: {edge_str}",
            f"> 生成时间: {self.result.get('timestamp', 'N/A')}",
            "",
        ]

        # Sections
        for section in sections:
            lines.append(f"## {section['title']}")
            lines.append("")
            lines.append(section["content"])
            lines.append("")

        # Aggregation table (always included)
        lines.append("## 聚合机制对比")
        lines.append("")
        lines.append("| 机制 | 概率 | 说明 |")
        lines.append("|------|------|------|")
        method_labels = {
            "simple_average": "简单平均",
            "median": "中位数",
            "trimmed_mean": "修剪平均",
            "logit_average": "对数平均",
            "extremized": "极化处理",
            "reputation_weighted": "信誉加权",
            "lmsr_market": "LMSR市场",
            "peer_prediction": "同行预测",
            "hybrid": "混合机制",
        }
        for method, info in agg.items():
            prob = info.get("probability")
            label = method_labels.get(method, method)
            prob_str = f"{prob:.1f}%" if prob is not None else "N/A"
            lines.append(f"| {label} | {prob_str} | {method} |")
        lines.append("")

        return "\n".join(lines)

    def _llm_call(self, prompt: str) -> str:
        """Make a single LLM call with a prompt string."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content or ""

    def _llm_call_messages(self, messages: list[dict]) -> str:
        """Make an LLM call with a full message history."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content or ""
