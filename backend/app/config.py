"""
Unified configuration module for prediction-market-debater.
Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)


class Config:
    """Central configuration. All settings as class attributes."""

    # ── Project paths ──────────────────────────────────────────────
    PROJECT_ROOT = _PROJECT_ROOT
    BASE_DIR = str(Path(__file__).resolve().parent)  # backend/app/
    PROMPTS_DIR = str(Path(__file__).resolve().parent / "prompts")
    DATA_DIR = str(_PROJECT_ROOT / "data")
    RESULTS_DIR = str(_PROJECT_ROOT / "data" / "results")
    UPLOAD_FOLDER = str(_PROJECT_ROOT / "uploads")

    # ── Flask ──────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    JSON_AS_ASCII = False

    # ── API Keys ───────────────────────────────────────────────────
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

    POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")

    # ── Auth & Billing ──────────────────────────────────────────────
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
    FREE_PREDICTIONS_PER_MONTH = 3

    # ── Debate parameters ──────────────────────────────────────────
    PREDICTION_SAMPLES = int(os.getenv("PREDICTION_SAMPLES", "1"))
    DEBATE_ROUNDS = int(os.getenv("DEBATE_ROUNDS", "3"))
    INFO_PARTITION_SHARED_RATIO = float(os.getenv("INFO_PARTITION_SHARED_RATIO", "0.4"))
    INFO_PARTITION_PRIVATE_COUNT = int(os.getenv("INFO_PARTITION_PRIVATE_COUNT", "2"))
    MAX_VIDEOS_PER_QUERY = int(os.getenv("MAX_VIDEOS_PER_QUERY", "15"))
    YOUTUBE_ORACLE_COUNT = int(os.getenv("YOUTUBE_ORACLE_COUNT", "5"))
    YOUTUBE_MAX_TRANSCRIPT_CHARS = int(os.getenv("YOUTUBE_MAX_TRANSCRIPT_CHARS", "8000"))
    MAX_RETRIEVAL_DOCS = int(os.getenv("MAX_RETRIEVAL_DOCS", "15"))
    REDDIT_USER_AGENT = "prediction-market-debater/1.0"

    # ── Report agent parameters ────────────────────────────────────
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.getenv("REPORT_AGENT_MAX_TOOL_CALLS", "5"))
    REPORT_AGENT_MAX_ITERATIONS = int(os.getenv("REPORT_AGENT_MAX_ITERATIONS", "5"))
    REPORT_AGENT_TEMPERATURE = float(os.getenv("REPORT_AGENT_TEMPERATURE", "0.5"))

    # ── Agent personas ─────────────────────────────────────────────
    AGENT_PERSONAS = [
        {"name": "乐观分析师", "stance": "bull", "description": "倾向寻找支持事件发生的证据，关注正面动力、历史先例中的成功案例", "style": "数据驱动，引用具体统计和趋势"},
        {"name": "质疑分析师", "stance": "bear", "description": "倾向质疑共识，寻找被忽视的风险和反面证据，关注基准率", "style": "批判性思维，关注过度自信偏差和尾部风险"},
        {"name": "贝叶斯分析师", "stance": "neutral", "description": "从基准率出发，严格按证据更新概率，不带情感倾向", "style": "概率推理，明确先验和后验，关注校准"},
        {"name": "历史类比师", "stance": "neutral", "description": "专注于寻找历史上的类似情境和先例，通过类比推理评估当前事件的可能性", "style": "叙事性强，善于引用历史案例和类比，从过去的模式中提取预测信号"},
        {"name": "数据统计师", "stance": "neutral", "description": "纯粹依赖数据和统计模型，排除主观判断，关注样本量和统计显著性", "style": "量化分析，引用具体数字、胜率、ELO评分、回归模型结果"},
        {"name": "情绪分析师", "stance": "bull", "description": "关注市场情绪、媒体叙事和公众舆论对结果的影响，捕捉动量效应", "style": "关注叙事转变、媒体报道频率、社交媒体情绪指标和市场动量"},
        {"name": "逆向投资者", "stance": "bear", "description": "系统性地质疑市场共识，寻找大众忽视的反向信号，相信均值回归", "style": "逆向思维，强调过度反应、锚定偏差和均值回归，喜欢押注冷门"},
        {"name": "基本面分析师", "stance": "neutral", "description": "深入分析事件的基本面因素（团队实力、资源、结构性优势），忽略短期噪音", "style": "结构化分析，关注长期趋势、资源对比、系统性优劣势"},
        {"name": "风险评估师", "stance": "bear", "description": "专注于识别和量化风险因素，关注黑天鹅事件和尾部分布", "style": "风险矩阵思维，列举风险因素及其影响概率，关注最坏情况"},
        {"name": "综合策略师", "stance": "neutral", "description": "综合多种分析框架，寻找各方法间的一致信号，擅长识别分析盲点", "style": "元分析视角，权衡不同方法论的优劣，寻找信号共振点"},
    ]

    # ── Aggregation parameters ─────────────────────────────────────
    REPUTATION_DECAY = float(os.getenv("REPUTATION_DECAY", "0.7"))
    LMSR_LIQUIDITY = float(os.getenv("LMSR_LIQUIDITY", "100.0"))
    HYBRID_LAMBDA_MARKET = float(os.getenv("HYBRID_LAMBDA_MARKET", "0.4"))
    HYBRID_LAMBDA_REPUTATION = float(os.getenv("HYBRID_LAMBDA_REPUTATION", "0.3"))
    HYBRID_LAMBDA_BTS = float(os.getenv("HYBRID_LAMBDA_BTS", "0.3"))
    EXTREMIZATION_D = float(os.getenv("EXTREMIZATION_D", "2.5"))

    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration. Returns a list of error strings (empty if valid)."""
        errors: list[str] = []

        # At least one LLM backend must be configured
        backends = cls.get_available_backends()
        if not backends:
            errors.append(
                "No LLM backend configured. Set at least one of: "
                "DEEPSEEK_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY"
            )

        # Hybrid lambdas should sum to 1.0
        lambda_sum = cls.HYBRID_LAMBDA_MARKET + cls.HYBRID_LAMBDA_REPUTATION + cls.HYBRID_LAMBDA_BTS
        if abs(lambda_sum - 1.0) > 1e-6:
            errors.append(
                f"HYBRID_LAMBDA values must sum to 1.0, got {lambda_sum:.4f}"
            )

        # Debate rounds must be positive
        if cls.DEBATE_ROUNDS < 1:
            errors.append(f"DEBATE_ROUNDS must be >= 1, got {cls.DEBATE_ROUNDS}")

        # Shared ratio must be between 0 and 1
        if not (0.0 <= cls.INFO_PARTITION_SHARED_RATIO <= 1.0):
            errors.append(
                f"INFO_PARTITION_SHARED_RATIO must be in [0, 1], got {cls.INFO_PARTITION_SHARED_RATIO}"
            )

        return errors

    @classmethod
    def get_available_backends(cls) -> list[dict]:
        """Return list of available LLM backend configurations."""
        backends = []
        if cls.DEEPSEEK_API_KEY:
            backends.append({
                "api_key": cls.DEEPSEEK_API_KEY,
                "base_url": cls.DEEPSEEK_BASE_URL,
                "model": cls.DEEPSEEK_MODEL,
                "label": "deepseek",
            })
        if cls.OPENAI_API_KEY:
            backends.append({
                "api_key": cls.OPENAI_API_KEY,
                "base_url": "https://api.openai.com/v1",
                "model": cls.OPENAI_MODEL,
                "label": "openai",
            })
        if cls.ANTHROPIC_API_KEY:
            backends.append({
                "api_key": cls.ANTHROPIC_API_KEY,
                "base_url": "https://api.anthropic.com/v1",
                "model": cls.ANTHROPIC_MODEL,
                "label": "anthropic",
            })
        if cls.GOOGLE_API_KEY:
            backends.append({
                "api_key": cls.GOOGLE_API_KEY,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": cls.GOOGLE_MODEL,
                "label": "google",
            })
        return backends
