"""
Configuration for Prediction Market Debater.

Set API keys via environment variables or .env file:
  DEEPSEEK_API_KEY="your-deepseek-api-key"
  TAVILY_API_KEY="your-tavily-api-key"
"""

import os
from pathlib import Path

# Load .env file if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# API Keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek V3

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"  # Cost-effective, still strong

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_MODEL = "gemini-2.0-flash"

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

# Multi-model backend configurations (OpenAI-compatible)
# Each entry: (api_key, base_url, model_name, label)
def get_available_backends() -> list[dict]:
    """Return list of available LLM backends based on configured API keys."""
    backends = []
    if DEEPSEEK_API_KEY:
        backends.append({
            "api_key": DEEPSEEK_API_KEY,
            "base_url": DEEPSEEK_BASE_URL,
            "model": DEEPSEEK_MODEL,
            "label": "deepseek",
        })
    if OPENAI_API_KEY:
        backends.append({
            "api_key": OPENAI_API_KEY,
            "base_url": "https://api.openai.com/v1",
            "model": OPENAI_MODEL,
            "label": "openai",
        })
    # Anthropic and Google use OpenAI-compatible endpoints via proxy or direct
    # Add more backends here as needed
    return backends

# Debate parameters
PREDICTION_SAMPLES = 1  # MVP: 1 sample per agent to save tokens
DEBATE_ROUNDS = 3       # 3-round debate

# Information partitioning parameters
INFO_PARTITION_SHARED_RATIO = 0.4   # 40% of docs shared by all agents
INFO_PARTITION_PRIVATE_COUNT = 2    # Each agent gets 2 private docs (others don't see)

# YouTube collection settings
MAX_VIDEOS_PER_QUERY = 15          # Videos to search per query
YOUTUBE_ORACLE_COUNT = 5           # Top-k docs marked as oracle (RAFT)
YOUTUBE_MAX_TRANSCRIPT_CHARS = 8000  # Truncate long transcripts

# 10 Agent personas with diverse analytical frameworks
AGENT_PERSONAS = [
    {
        "name": "乐观分析师",
        "stance": "bull",
        "description": "倾向寻找支持事件发生的证据，关注正面动力、历史先例中的成功案例",
        "style": "数据驱动，引用具体统计和趋势",
    },
    {
        "name": "质疑分析师",
        "stance": "bear",
        "description": "倾向质疑共识，寻找被忽视的风险和反面证据，关注基准率",
        "style": "批判性思维，关注过度自信偏差和尾部风险",
    },
    {
        "name": "贝叶斯分析师",
        "stance": "neutral",
        "description": "从基准率出发，严格按证据更新概率，不带情感倾向",
        "style": "概率推理，明确先验和后验，关注校准",
    },
    {
        "name": "历史类比师",
        "stance": "neutral",
        "description": "专注于寻找历史上的类似情境和先例，通过类比推理评估当前事件的可能性",
        "style": "叙事性强，善于引用历史案例和类比，从过去的模式中提取预测信号",
    },
    {
        "name": "数据统计师",
        "stance": "neutral",
        "description": "纯粹依赖数据和统计模型，排除主观判断，关注样本量和统计显著性",
        "style": "量化分析，引用具体数字、胜率、ELO评分、回归模型结果",
    },
    {
        "name": "情绪分析师",
        "stance": "bull",
        "description": "关注市场情绪、媒体叙事和公众舆论对结果的影响，捕捉动量效应",
        "style": "关注叙事转变、媒体报道频率、社交媒体情绪指标和市场动量",
    },
    {
        "name": "逆向投资者",
        "stance": "bear",
        "description": "系统性地质疑市场共识，寻找大众忽视的反向信号，相信均值回归",
        "style": "逆向思维，强调过度反应、锚定偏差和均值回归，喜欢押注冷门",
    },
    {
        "name": "基本面分析师",
        "stance": "neutral",
        "description": "深入分析事件的基本面因素（团队实力、资源、结构性优势），忽略短期噪音",
        "style": "结构化分析，关注长期趋势、资源对比、系统性优劣势",
    },
    {
        "name": "风险评估师",
        "stance": "bear",
        "description": "专注于识别和量化风险因素，关注黑天鹅事件和尾部分布",
        "style": "风险矩阵思维，列举风险因素及其影响概率，关注最坏情况",
    },
    {
        "name": "综合策略师",
        "stance": "neutral",
        "description": "综合多种分析框架，寻找各方法间的一致信号，擅长识别分析盲点",
        "style": "元分析视角，权衡不同方法论的优劣，寻找信号共振点",
    },
]

# Aggregation mechanism parameters
REPUTATION_DECAY = 0.7          # α in reputation update rule
LMSR_LIQUIDITY = 100.0          # LMSR market maker liquidity parameter b
HYBRID_LAMBDA_MARKET = 0.4      # Weight for LMSR component in hybrid
HYBRID_LAMBDA_REPUTATION = 0.3  # Weight for reputation component in hybrid
HYBRID_LAMBDA_BTS = 0.3         # Weight for BTS component in hybrid
EXTREMIZATION_D = 2.5           # Extremization parameter (Baron et al., 2014)

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
