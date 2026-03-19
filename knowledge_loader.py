"""
Expert knowledge loader for Level 2 AI Clone generation.

Loads domain-specific knowledge profiles (few-shot examples, analytical frameworks,
typical phrases) and injects them into expert system prompts.

Each expert's knowledge profile transforms a generic LLM into a specialized
domain expert by providing:
  1. Core analytical framework and methodology
  2. Few-shot examples of real analysis in their style
  3. Typical phrases and mannerisms for consistency
"""

import os

# Map expert names to their knowledge profile files
KNOWLEDGE_MAP = {
    # Crypto experts
    "链上数据分析师": "crypto/onchain_analyst.md",
    "宏观经济学家": "crypto/macro_economist.md",
    "加密原生研究员": "crypto/crypto_researcher.md",
    "风险管理顾问": "crypto/risk_consultant.md",
    "监管政策专家": "crypto/regulatory_expert.md",
    # Sports experts
    "数据统计专家": "sports/statistician.md",
    "战术分析师": "sports/tactical_analyst.md",
    "伤病体能专家": "sports/injury_analyst.md",
    "博彩市场分析师": "sports/betting_analyst.md",
    "资深体育评论员": "sports/commentator.md",
}

_KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expert_knowledge")

# Cache loaded knowledge to avoid repeated file I/O
_cache: dict[str, str] = {}


def load_expert_knowledge(expert_name: str) -> str:
    """
    Load the knowledge profile for a given expert.

    Returns the full markdown content, or empty string if not found.
    """
    if expert_name in _cache:
        return _cache[expert_name]

    filename = KNOWLEDGE_MAP.get(expert_name)
    if not filename:
        return ""

    filepath = os.path.join(_KNOWLEDGE_DIR, filename)
    if not os.path.exists(filepath):
        return ""

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    _cache[expert_name] = content
    return content


def build_clone_prompt(
    expert_name: str,
    role: str,
    description: str,
    style: str,
    expertise: list[str],
    context_text: str,
) -> str:
    """
    Build a complete system prompt for an AI Clone expert.

    Combines:
      1. Base persona definition
      2. Knowledge profile (framework + few-shot examples + mannerisms)
      3. RAG context for the current topic
      4. Behavioral instructions

    This is the core of Level 2 cloning - the knowledge profile provides
    the expert's "memory" and analytical DNA.
    """
    knowledge = load_expert_knowledge(expert_name)

    # Build the prompt in layers
    sections = []

    # Layer 1: Identity
    sections.append(f"""你是 {expert_name}（{role}）— {description}

分析风格：{style}
专业领域：{"、".join(expertise)}""")

    # Layer 2: Knowledge Profile (the "clone DNA")
    if knowledge:
        sections.append(f"""=== EXPERT KNOWLEDGE PROFILE ===
以下是你的专业知识档案，包含你的分析框架、典型案例和表达风格。
你必须严格按照这个档案中的方法论和风格进行分析。

{knowledge}
=== END KNOWLEDGE PROFILE ===""")

    # Layer 3: Behavioral instructions
    sections.append("""=== BEHAVIORAL INSTRUCTIONS ===
你正在参与一个专家咨询会议。一位用户带着自己的观点来寻求专业意见。

核心行为准则：
1. 严格保持你的专业角色和分析风格——参考上面的 Knowledge Profile
2. 使用你的分析框架和方法论来评估用户观点
3. 引用你 Knowledge Profile 中的典型表达方式和分析模式
4. 以你的专业视角诚实评估——不讨好用户，也不刻意唱反调
5. 给出具体、可操作的建议，而非模糊的"要小心"
6. 如果你的专业领域之外的问题，坦诚说明并建议咨询其他专家
=== END INSTRUCTIONS ===""")

    # Layer 4: RAG context
    if context_text:
        sections.append(f"""=== CURRENT TOPIC CONTEXT ===
以下是与当前话题相关的背景资料（新闻、视频字幕等）。
注意：部分文档可能是干扰信息，请自行判断相关性。
引用时使用格式：##begin_quote## 引用内容 ##end_quote## [文档 X]

{context_text}
=== END CONTEXT ===""")

    return "\n\n".join(sections)
