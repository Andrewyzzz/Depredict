#!/usr/bin/env python3
"""
DePredict Polymarket 回测报告 — 中文 PDF 版

生成多页 PDF 报告，包含：
  - 封面
  - 摘要
  - 方法论详述（信号生成、凯利公式、聚合机制）
  - 结果图表（资金曲线、机制对比、Brier 评分、敏感性分析）
  - 逐笔交易明细
  - 结论与建议

用法：
    python scripts/backtest_pdf_report_cn.py
    python scripts/backtest_pdf_report_cn.py -o reports/backtest_report_cn.pdf
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
DATA_PATH = PROJECT_ROOT / "data" / "prospective" / "predictions.json"

# ── 色彩 ─────────────────────────────────────────────────────────────────────
C = {
    "bg":       "#111317",
    "surface":  "#1a1c20",
    "card":     "#1e2024",
    "border":   "#2a2c32",
    "primary":  "#adc6ff",
    "blue":     "#4d8eff",
    "text":     "#e2e2e8",
    "dim":      "#8a8e9c",
    "green":    "#4ae176",
    "red":      "#ff6b6b",
    "amber":    "#f0b90b",
    "purple":   "#b48eff",
    "cyan":     "#56d4e0",
    "orange":   "#ff9f43",
    "pink":     "#ff6b9d",
}

MECH_LABELS = {
    "simple_average":      "简单平均",
    "median":              "中位数",
    "trimmed_mean":        "截断均值",
    "logit_average":       "Logit均值",
    "extremized":          "极端化",
    "reputation_weighted": "声誉加权",
    "lmsr_market":         "LMSR市场",
    "peer_prediction":     "同行预测",
    "hybrid":              "混合(M4)",
}
ALL_MECHANISMS = list(MECH_LABELS.keys())

CRYPTO_KW = ["bitcoin", "ethereum", "btc", "eth", "crypto", "solana",
             "sol", "xrp", "bnb", "doge", "dogecoin", "defi"]

# ── 中文字体 ──────────────────────────────────────────────────────────────────
CN_FONT = "Arial Unicode MS"  # macOS 内置，覆盖简繁体

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": [CN_FONT, "PingFang HK", "Songti SC", "STHeiti", "Heiti TC"],
    "font.size": 9,
    "axes.facecolor": C["surface"],
    "figure.facecolor": C["bg"],
    "text.color": C["text"],
    "axes.edgecolor": C["border"],
    "axes.labelcolor": C["dim"],
    "xtick.color": C["dim"],
    "ytick.color": C["dim"],
    "grid.color": C["border"],
    "grid.alpha": 0.4,
    "axes.grid": True,
    "axes.grid.which": "major",
    "legend.facecolor": C["surface"],
    "legend.edgecolor": C["border"],
    "legend.fontsize": 8,
    "axes.unicode_minus": False,
    "mathtext.default": "regular",
})

# Monospace font that supports CJK — fallback to sans-serif
MONO = CN_FONT


def new_page(pdf, figsize=(11.69, 8.27)):
    fig = plt.figure(figsize=figsize, facecolor=C["bg"])
    return fig


def save_page(pdf, fig):
    pdf.savefig(fig, facecolor=C["bg"])
    plt.close(fig)


# ── 数据 & 模拟 ──────────────────────────────────────────────────────────────

def is_crypto(pred):
    t = (pred.get("slug", "") + " " + pred.get("question", "")).lower()
    return any(k in t for k in CRYPTO_KW)


def load_data():
    with open(DATA_PATH) as f:
        raw = json.load(f)
    resolved = [p for p in raw if p["status"] == "resolved" and p["resolution"] is not None]
    rows = []
    for p in resolved:
        mechs = p.get("all_mechanisms", {})
        row = {
            "question": p["question"], "slug": p["slug"],
            "category": "加密货币" if is_crypto(p) else "非加密货币",
            "market_price": p["market_price_at_prediction"],
            "resolution": p["resolution"],
            "model_brier": p.get("model_brier"),
            "market_brier": p.get("market_brier"),
            "predicted_at": pd.to_datetime(p["predicted_at"]),
        }
        for m in ALL_MECHANISMS:
            row[f"prob_{m}"] = mechs.get(m)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("predicted_at").reset_index(drop=True)


def kelly_fraction(p, mkt, side):
    if side == "YES":
        b = (1.0 - mkt) / mkt
        f = (p * b - (1.0 - p)) / b
    else:
        b = mkt / (1.0 - mkt)
        f = ((1.0 - p) * b - p) / b
    return max(f, 0.0)


def simulate(df, mechanism, kelly_mult=0.5, min_edge=0.0, bankroll=1000.0):
    records = []
    bank = bankroll
    for _, row in df.iterrows():
        v = row.get(f"prob_{mechanism}")
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        p = v / 100.0
        mkt = row["market_price"]
        edge = p - mkt
        if abs(edge) < min_edge:
            continue
        side = "YES" if edge > 0 else "NO"
        kf = kelly_fraction(p, mkt, side) * kelly_mult
        if kf <= 0:
            continue
        bet = bank * kf
        if side == "YES":
            pnl = bet * (1.0 - mkt) / mkt if row["resolution"] else -bet
            win = bool(row["resolution"])
        else:
            pnl = bet * mkt / (1.0 - mkt) if not row["resolution"] else -bet
            win = not row["resolution"]
        bank += pnl
        records.append({
            "question": row["question"], "category": row["category"],
            "predicted_at": row["predicted_at"],
            "side": side, "p": p, "mkt": mkt, "edge": abs(edge),
            "kf": kf, "bet": bet, "pnl": pnl, "win": win, "bank": bank,
        })
    return pd.DataFrame(records)


def stats(sim, bankroll=1000.0):
    if sim.empty:
        return dict(n=0, wins=0, wr=0, pnl=0, roi=0, sharpe=0, maxdd=0, final=bankroll)
    n = len(sim)
    w = int(sim["win"].sum())
    pnl = sim["pnl"].sum()
    roi = pnl / bankroll * 100
    r = sim["pnl"] / sim["bet"]
    sharpe = r.mean() / r.std() if r.std() > 0 else 0
    eq = np.array([bankroll] + sim["bank"].tolist())
    pk = np.maximum.accumulate(eq)
    dd = ((pk - eq) / np.where(pk > 0, pk, 1)).max() * 100
    return dict(n=n, wins=w, wr=w / n * 100, pnl=pnl, roi=roi,
                sharpe=sharpe, maxdd=dd, final=bankroll + pnl)


# ── 页面 ─────────────────────────────────────────────────────────────────────

def page_cover(pdf, df):
    fig = new_page(pdf)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_facecolor(C["bg"])

    ax.plot([0.08, 0.92], [0.62, 0.62], color=C["blue"], linewidth=2, alpha=0.6)
    ax.plot([0.08, 0.35], [0.61, 0.61], color=C["blue"], linewidth=4)

    ax.text(0.5, 0.78, "DEPREDICT", fontsize=42, fontweight="bold",
            color=C["primary"], ha="center", va="center", fontfamily=MONO)
    ax.text(0.5, 0.70, "Polymarket 回测报告", fontsize=24,
            color=C["text"], ha="center", va="center")
    ax.text(0.5, 0.55, "AI多专家辩论系统能否在预测市场中产生超额收益？",
            fontsize=14, color=C["dim"], ha="center", va="center")

    n_total = len(df)
    n_crypto = len(df[df["category"] == "加密货币"])
    n_nc = len(df[df["category"] == "非加密货币"])
    date_range = f"{df['predicted_at'].min().strftime('%Y-%m-%d')}  ~  {df['predicted_at'].max().strftime('%Y-%m-%d')}"

    info = (f"已结算预测: {n_total}  |  非加密: {n_nc}  |  加密: {n_crypto}\n"
            f"时间跨度: {date_range}\n"
            f"策略: 凯利公式 (Half-Kelly)  |  初始资金: $1,000")
    ax.text(0.5, 0.38, info, fontsize=11, color=C["dim"], ha="center", va="center",
            linespacing=1.8)

    ax.text(0.5, 0.12, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            fontsize=9, color=C["border"], ha="center")
    ax.text(0.5, 0.08, "github.com/Andrewyzzz/Depredict", fontsize=8,
            color=C["border"], ha="center", style="italic")

    save_page(pdf, fig)


def page_executive_summary(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("摘要", fontsize=20, color=C["primary"], fontweight="bold", y=0.95)

    sim_all = simulate(df, "hybrid")
    sim_nc = simulate(df[df["category"] == "非加密货币"], "hybrid")
    sim_cr = simulate(df[df["category"] == "加密货币"], "hybrid")
    s_all, s_nc, s_cr = stats(sim_all), stats(sim_nc), stats(sim_cr)

    model_b = df["model_brier"].dropna().mean()
    market_b = df["market_brier"].dropna().mean()
    brier_wins = int((df["model_brier"] < df["market_brier"]).sum())

    ax = fig.add_axes([0.05, 0.62, 0.9, 0.28])
    ax.axis("off")
    ax.set_xlim(0, 6); ax.set_ylim(0, 2)

    kpis = [
        ("总体 ROI", f"{s_all['roi']:+.1f}%", s_all["roi"] > 0),
        ("非加密 ROI", f"{s_nc['roi']:+.1f}%", s_nc["roi"] > 0),
        ("加密 ROI", f"{s_cr['roi']:+.1f}%", s_cr["roi"] > 0),
        ("总胜率", f"{s_all['wr']:.1f}%", s_all["wr"] > 50),
        ("Brier 优势", f"{market_b - model_b:+.4f}", market_b > model_b),
        ("Brier 胜场", f"{brier_wins}/{len(df)}", brier_wins > len(df) / 2),
    ]
    for i, (label, value, positive) in enumerate(kpis):
        x = i
        color = C["green"] if positive else C["red"]
        rect = mpatches.FancyBboxPatch((x + 0.05, 0.1), 0.9, 1.8,
                                       boxstyle="round,pad=0.05",
                                       facecolor=C["card"], edgecolor=C["border"])
        ax.add_patch(rect)
        ax.text(x + 0.5, 1.5, label, fontsize=7.5, color=C["dim"],
                ha="center", va="center", fontweight="bold")
        ax.text(x + 0.5, 0.85, value, fontsize=16, color=color,
                ha="center", va="center", fontweight="bold", fontfamily=MONO)

    ax2 = fig.add_axes([0.08, 0.22, 0.84, 0.32])
    ax2.axis("off")
    ax2.set_xlim(0, 10); ax2.set_ylim(0, 5)

    headers = ["类别", "交易数", "胜率", "ROI", "盈亏", "夏普比", "最大回撤", "最终资金"]
    rows_data = [("全部", s_all), ("非加密", s_nc), ("加密", s_cr)]

    for j, h in enumerate(headers):
        ax2.text(j * 1.25, 4.5, h, fontsize=7.5, color=C["dim"],
                 fontweight="bold", ha="center", va="center")
    ax2.plot([0, 10], [4.15, 4.15], color=C["border"], linewidth=0.5)

    for i, (label, s) in enumerate(rows_data):
        y = 3.5 - i * 1.0
        color = C["green"] if s["roi"] > 0 else C["red"]
        vals = [label, str(s["n"]), f"{s['wr']:.1f}%", f"{s['roi']:+.1f}%",
                f"${s['pnl']:+,.0f}", f"{s['sharpe']:+.2f}",
                f"{s['maxdd']:.1f}%", f"${s['final']:,.0f}"]
        for j, v in enumerate(vals):
            c = color if j in (3, 4) else C["text"]
            ax2.text(j * 1.25, y, v, fontsize=9, color=c,
                     ha="center", va="center", fontfamily=MONO)
        ax2.plot([0, 10], [y - 0.4, y - 0.4], color=C["border"], linewidth=0.3, alpha=0.5)

    ax3 = fig.add_axes([0.08, 0.04, 0.84, 0.14])
    ax3.axis("off")
    finding = (
        f"核心发现：DePredict 在非加密货币市场表现出显著的超额收益（ROI {s_nc['roi']:+.0f}%，"
        f"胜率 {s_nc['wr']:.0f}%），但在加密货币预测中持续亏损（ROI {s_cr['roi']:+.0f}%）。"
        f"最优策略：仅在非加密货币市场部署资金，采用 Half-Kelly 仓位管理。"
    )
    ax3.text(0.02, 0.5, finding, fontsize=9.5, color=C["text"],
             va="center", wrap=True,
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a2a3a", edgecolor=C["blue"], alpha=0.8))

    save_page(pdf, fig)


def page_methodology_1(pdf):
    fig = new_page(pdf)
    fig.suptitle("方法论 — 系统架构与信号生成", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    y = 9.8
    sections = [
        ("1. DePredict 多专家辩论系统", [
            "DePredict 组建了 10 个 AI 专家 Agent，每个 Agent 拥有独特的分析立场",
            "（看多、看空、中性）和领域专属知识库，就二元预测市场问题进行结构化辩论。",
            "系统不依赖单一模型输出，而是通过「结构化认知冲突」迫使专家暴露盲点、",
            "质疑彼此的推理逻辑，最终收敛到校准后的概率预测。",
            "",
            "10 个 Agent 涵盖多元分析视角：",
            "  · 乐观分析师（看多）        · 质疑分析师（看空）",
            "  · 贝叶斯分析师（中性）      · 历史类比师（中性）",
            "  · 数据统计师（中性）        · 情绪分析师（看多）",
            "  · 逆向投资者（看空）        · 基本面分析师（中性）",
            "  · 风险评估师（看空）        · 综合策略师（中性）",
        ]),
        ("2. 三轮辩论流程", [
            "第一轮 — 独立预测：每个 Agent 接收 RAG 检索文档（YouTube 转录 + Tavily 新闻），",
            "  独立产出概率估计（0-100%）及推理过程。文档分配采用信息分区机制：",
            "  40% 共享文档 + 60% 私有文档，确保真正的信息不对称。",
            "",
            "第二轮 — 交叉反驳：Agent 看到所有第一轮预测和推理后，",
            "  撰写反驳意见，质疑特定论点。Agent 可据此修正自己的概率。",
            "",
            "第三轮 — 最终预测：阅读所有反驳后，每个 Agent 提交最终概率，",
            "  融合辩论中最有力的论据。",
        ]),
        ("3. 九种聚合机制", [
            "10 个 Agent 的最终预测通过 9 种独立机制聚合：",
            "",
            "  · 简单平均 — 所有 Agent 概率的算术平均",
            "  · 中位数 — 对极端预测稳健",
            "  · 截断均值 — 去除最高/最低 10% 后取均值",
            "  · Logit 均值 — 在对数几率空间聚合（更好处理极端值）",
            "  · 极端化均值 — 将共识推离 50%（Baron et al. 2014）",
            "  · 声誉加权 — 按历史 Brier Score 表现加权",
            "  · LMSR 市场 — Hanson 对数市场评分规则 + Kelly 仓位",
            "  · 同行预测 (BTS) — 贝叶斯真相血清，通过元预测评分",
            "  · 混合 (M4) — 加权融合：0.4×LMSR + 0.3×声誉 + 0.3×BTS",
            "",
            "本次回测主要使用混合（M4）机制作为交易信号。",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=11, color=C["blue"], fontweight="bold")
        y -= 0.35
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"])
            y -= 0.28
        y -= 0.25

    save_page(pdf, fig)


def page_methodology_2(pdf):
    fig = new_page(pdf)
    fig.suptitle("方法论 — 交易策略与仓位管理", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    y = 9.8
    sections = [
        ("4. 交易信号生成", [
            "Polymarket 是二元预测市场：YES 份额以价格 P_mkt (0,1) 交易，",
            "事件发生则支付 $1，否则为 $0。市场价格等于隐含概率。",
            "交易信号利用 DePredict 模型概率 P_model 与市场价格 P_mkt 的偏差。",
            "",
            "信号逻辑：",
            "  P_model > P_mkt  =>  买入 YES（模型认为事件概率高于市场）",
            "  P_model < P_mkt  =>  买入 NO （模型认为事件概率低于市场）",
            "  边际 Edge = |P_model - P_mkt|",
            "",
            "盈亏计算：",
            "  买入YES 成本P_mkt => 事件发生: 利润 = 赌注 x (1-P_mkt)/P_mkt",
            "                    => 事件未发生: 亏损 = -赌注",
            "  买入NO  成本(1-P_mkt) => 事件未发生: 利润 = 赌注 x P_mkt/(1-P_mkt)",
            "                       => 事件发生:   亏损 = -赌注",
        ]),
        ("5. 凯利公式（Kelly Criterion）仓位管理", [
            "凯利公式确定最优下注比例，最大化长期几何增长率同时避免破产。",
            "",
            "买入 YES 时（净赔率 b = (1 - P_mkt) / P_mkt）：",
            "",
            "              P_model x b  -  (1 - P_model)",
            "  f* =  ──────────────────────────────────────",
            "                          b",
            "",
            "买入 NO 时（净赔率 b = P_mkt / (1 - P_mkt)）：",
            "",
            "              (1 - P_model) x b  -  P_model",
            "  f* =  ────────────────────────────────────────",
            "                            b",
            "",
            "其中 f* 为下注占总资金的比例。若 f* <= 0，则跳过该交易。",
        ]),
        ("6. Half-Kelly 与风险控制", [
            "全凯利虽理论最优，但前提是概率估计完全准确。实际中模型存在误差，",
            "全凯利会导致过度下注、极端波动和深度回撤。",
            "",
            "我们默认使用 Half-Kelly（f = 0.5 x f*），其优势：",
            "  · 保留全凯利约 75% 的长期增长率",
            "  · 将方差降低约一半",
            "  · 大幅降低最大回撤",
            "  · 对概率估计误差更具鲁棒性",
            "",
            "本报告对 Kelly 系数 0.1x ~ 1.0x 进行了敏感性分析。",
            "",
            "其他测试参数：",
            "  · 最小边际阈值 — 仅在 |P_model - P_mkt| > 阈值时交易",
            "  · 类别过滤 — 分别评估加密货币 vs 非加密货币表现",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=11, color=C["blue"], fontweight="bold")
        y -= 0.35
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"])
            y -= 0.28
        y -= 0.25

    save_page(pdf, fig)


def page_methodology_3(pdf):
    fig = new_page(pdf)
    fig.suptitle("方法论 — 评估体系", fontsize=18,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    y = 9.8
    sections = [
        ("7. 盈利指标", [
            "  · 总盈亏（P&L）— 相对初始资金的绝对盈亏金额",
            "  · 投资回报率（ROI）— P&L / 初始资金 x 100%",
            "  · 胜率 — 盈利交易占总交易数的比例",
            "  · 夏普比率 — 每笔交易收益率均值 / 标准差",
            "    衡量风险调整后收益；>0.5 为良好，>1.0 为优秀",
            "  · 最大回撤 — 峰值到谷底的最大跌幅占峰值百分比",
            "    衡量最坏情况下的资金侵蚀程度",
        ]),
        ("8. 预测质量指标", [
            "  · Brier 评分 — (预测概率 - 实际结果)^2，结果为 0 或 1",
            "    范围 0（完美）到 1（最差）；越低越好",
            "  · 模型 vs 市场 Brier — 对比 DePredict Brier 与市场隐含 Brier",
            "    若模型 Brier < 市场 Brier，说明模型预测更准确",
            "  · 边际分布 — (P_model - P_mkt) 的直方图，按盈亏着色",
            "    揭示大边际是否与胜利相关",
        ]),
        ("9. 敏感性维度", [
            "  · Kelly 系数（0.1x ~ 1.0x）— 寻找最优风险水平",
            "  · 边际阈值（0% ~ 20%）— 过滤低信心信号",
            "  · 聚合机制（9 种方法）— 哪种聚合器最赚钱",
            "  · 类别（加密 vs 非加密）— 领域专属表现",
        ]),
        ("10. 回测假设与约束", [
            "  · 以记录的市场价格成交（无滑点模型）",
            "  · 默认无交易成本（Polymarket 无手续费，但存在买卖价差）",
            "  · 顺序交易，每笔结算后更新资金",
            "  · 无前视偏差：仅使用预测时刻的市场价格",
            "  · 无仓位限制和流动性约束",
            "  · 所有预测使用相同 Kelly 乘数（无自适应调整）",
        ]),
        ("11. 数据采集", [
            "  · 市场来源：Polymarket API (gamma-api.polymarket.com)",
            "  · 预过滤：排除极端价格（<5% 或 >95%）、衍生品市场、",
            "    地缘政治/暴力相关话题",
            "  · 结算状态通过 API 轮询自动检查",
            "  · 时间跨度：2026年3月18日 ~ 24日（7天实盘预测）",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=11, color=C["blue"], fontweight="bold")
        y -= 0.35
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"])
            y -= 0.28
        y -= 0.2

    save_page(pdf, fig)


def page_equity_curve(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("资金曲线 — 混合机制 (Half-Kelly)", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)
    ax = fig.add_subplot(111)

    bankroll = 1000.0
    for label, cat, color, ls in [
        ("非加密", "非加密货币", C["green"], "-"),
        ("加密", "加密货币", C["red"], "--"),
        ("全部市场", None, C["blue"], "-"),
    ]:
        sub = df if cat is None else df[df["category"] == cat]
        sim = simulate(sub, "hybrid", bankroll=bankroll)
        if sim.empty:
            continue
        eq = [bankroll] + sim["bank"].tolist()
        ax.plot(range(len(eq)), eq, label=label, color=color,
                linewidth=2 if cat is None else 1.8, linestyle=ls)

    ax.axhline(y=bankroll, color=C["dim"], linestyle=":", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("交易序号", fontsize=10)
    ax.set_ylabel("资金 ($)", fontsize=10)
    ax.legend(loc="upper left")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_mechanism_comparison(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("各聚合机制 ROI 对比", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_subplot(111)
    x = np.arange(len(ALL_MECHANISMS))
    w = 0.25

    for i, (label, cat, color) in enumerate([
        ("全部", None, C["blue"]),
        ("非加密", "非加密货币", C["green"]),
        ("加密", "加密货币", C["red"]),
    ]):
        rois = []
        for m in ALL_MECHANISMS:
            sub = df if cat is None else df[df["category"] == cat]
            sim = simulate(sub, m)
            roi = sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0
            rois.append(roi)
        bars = ax.bar(x + i * w - w, rois, w, label=label, color=color, alpha=0.85)
        for bar, roi in zip(bars, rois):
            if abs(roi) > 10:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f"{roi:+.0f}%", ha="center", va="bottom" if roi > 0 else "top",
                        fontsize=6, color=C["dim"])

    ax.set_xticks(x)
    ax.set_xticklabels([MECH_LABELS[m] for m in ALL_MECHANISMS], fontsize=7.5, rotation=30, ha="right")
    ax.set_ylabel("ROI (%)", fontsize=10)
    ax.axhline(y=0, color=C["text"], linewidth=0.8)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_brier_and_edge(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("预测质量 — Brier 评分与边际分布", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax1 = fig.add_subplot(121)
    for cat, color, marker in [("非加密货币", C["green"], "o"), ("加密货币", C["red"], "D")]:
        sub = df[df["category"] == cat]
        ax1.scatter(sub["market_brier"], sub["model_brier"],
                    c=color, marker=marker, alpha=0.7, s=40, label=cat, edgecolors="white", linewidths=0.3)
    ax1.plot([0, 0.8], [0, 0.8], color=C["dim"], linestyle=":", linewidth=1, label="模型=市场")
    ax1.set_xlabel("市场 Brier", fontsize=9)
    ax1.set_ylabel("模型 Brier", fontsize=9)
    ax1.set_xlim(0, 0.75); ax1.set_ylim(0, 0.75)
    ax1.legend(fontsize=7)
    ax1.set_title("模型 vs 市场 Brier 评分", fontsize=10, color=C["primary"])
    ax1.text(0.55, 0.15, "模型更优", fontsize=8, color=C["green"], alpha=0.6)
    ax1.text(0.1, 0.6, "市场更优", fontsize=8, color=C["red"], alpha=0.6)

    ax2 = fig.add_subplot(122)
    sim = simulate(df, "hybrid")
    if not sim.empty:
        wins = sim[sim["win"]]
        losses = sim[~sim["win"]]
        signed_edge_w = wins["edge"] * wins["side"].map({"YES": 1, "NO": -1})
        signed_edge_l = losses["edge"] * losses["side"].map({"YES": 1, "NO": -1})
        ax2.hist(signed_edge_w, bins=15, color=C["green"], alpha=0.6, label="盈利")
        ax2.hist(signed_edge_l, bins=15, color=C["red"], alpha=0.6, label="亏损")
    ax2.axvline(x=0, color=C["dim"], linestyle=":", linewidth=0.8)
    ax2.set_xlabel("有向边际（模型 - 市场）", fontsize=9)
    ax2.set_ylabel("次数", fontsize=9)
    ax2.legend(fontsize=7)
    ax2.set_title("边际分布与盈亏关系", fontsize=10, color=C["primary"])

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_subcategory(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("细分类别表现", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    def sub_cat(slug):
        s = slug.lower()
        if any(k in s for k in CRYPTO_KW): return "加密"
        if s.startswith("nba"): return "NBA"
        if s.startswith("nhl"): return "NHL"
        if s.startswith("cbb"): return "CBB"
        if s.startswith("epl") or s.startswith("uel"): return "足球"
        if s.startswith("lol") or s.startswith("cs2"): return "电竞"
        return "其他"

    sim = simulate(df, "hybrid")
    if sim.empty:
        save_page(pdf, fig); return

    sim["sub_cat"] = sim["question"].map(
        lambda q: sub_cat(df[df["question"] == q]["slug"].iloc[0] if len(df[df["question"] == q]) > 0 else ""))

    grouped = sim.groupby("sub_cat").agg(n=("win", "count"), wins=("win", "sum"), pnl=("pnl", "sum"))
    grouped["wr"] = grouped["wins"] / grouped["n"] * 100
    grouped = grouped.sort_values("pnl", ascending=True)

    ax1 = fig.add_subplot(121)
    colors_bar = [C["green"] if v > 0 else C["red"] for v in grouped["pnl"]]
    ax1.barh(grouped.index, grouped["pnl"], color=colors_bar, alpha=0.85)
    ax1.set_xlabel("盈亏 ($)", fontsize=9)
    ax1.set_title("各类别盈亏", fontsize=10, color=C["primary"])
    ax1.axvline(x=0, color=C["dim"], linewidth=0.8)
    for i, (idx, row) in enumerate(grouped.iterrows()):
        ax1.text(row["pnl"], i, f"  ${row['pnl']:+,.0f}", va="center", fontsize=7,
                 color=C["green"] if row["pnl"] > 0 else C["red"])

    ax2 = fig.add_subplot(122)
    colors_wr = [C["green"] if v > 50 else C["amber"] if v >= 40 else C["red"] for v in grouped["wr"]]
    ax2.barh(grouped.index, grouped["wr"], color=colors_wr, alpha=0.85)
    ax2.axvline(x=50, color=C["dim"], linestyle=":", linewidth=0.8)
    ax2.set_xlabel("胜率 (%)", fontsize=9)
    ax2.set_title("各类别胜率", fontsize=10, color=C["primary"])
    for i, (idx, row) in enumerate(grouped.iterrows()):
        ax2.text(row["wr"] + 1, i, f"{row['wr']:.0f}% ({int(row['wins'])}/{int(row['n'])})",
                 va="center", fontsize=7, color=C["dim"])

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_sensitivity(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("敏感性分析", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax1 = fig.add_subplot(121)
    fracs = np.arange(0.05, 1.05, 0.05)
    for label, cat, color in [("全部", None, C["blue"]), ("非加密", "非加密货币", C["green"]), ("加密", "加密货币", C["red"])]:
        rois = []
        for kf in fracs:
            sub = df if cat is None else df[df["category"] == cat]
            sim = simulate(sub, "hybrid", kelly_mult=kf)
            rois.append(sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0)
        ax1.plot(fracs, rois, color=color, label=label, linewidth=2, marker="o", markersize=3)
    ax1.axhline(y=0, color=C["dim"], linestyle=":", linewidth=0.8)
    ax1.set_xlabel("Kelly 系数", fontsize=9)
    ax1.set_ylabel("ROI (%)", fontsize=9)
    ax1.legend(fontsize=7)
    ax1.set_title("Kelly 系数 vs ROI", fontsize=10, color=C["primary"])

    ax2 = fig.add_subplot(122)
    thresholds = np.arange(0, 0.21, 0.01)
    for label, cat, color in [("全部", None, C["blue"]), ("非加密", "非加密货币", C["green"]), ("加密", "加密货币", C["red"])]:
        rois = []
        for thr in thresholds:
            sub = df if cat is None else df[df["category"] == cat]
            sim = simulate(sub, "hybrid", min_edge=thr)
            rois.append(sim["pnl"].sum() / 1000 * 100 if not sim.empty else 0)
        ax2.plot(thresholds * 100, rois, color=color, label=label, linewidth=2, marker="o", markersize=3)
    ax2.axhline(y=0, color=C["dim"], linestyle=":", linewidth=0.8)
    ax2.set_xlabel("最小边际阈值 (%)", fontsize=9)
    ax2.set_ylabel("ROI (%)", fontsize=9)
    ax2.legend(fontsize=7)
    ax2.set_title("边际阈值 vs ROI", fontsize=10, color=C["primary"])

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_waterfall(pdf, df, category, title_label):
    sub = df if category is None else df[df["category"] == category]
    sim = simulate(sub, "hybrid")
    if sim.empty:
        return

    fig = new_page(pdf)
    fig.suptitle(f"逐笔盈亏瀑布图 — {title_label}", fontsize=16,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_subplot(111)
    n = len(sim)
    cumulative = 0
    bottoms, heights, colors = [], [], []
    for _, r in sim.iterrows():
        bottoms.append(cumulative if r["pnl"] >= 0 else cumulative + r["pnl"])
        heights.append(abs(r["pnl"]))
        colors.append(C["green"] if r["pnl"] >= 0 else C["red"])
        cumulative += r["pnl"]

    ax.bar(range(n), heights, bottom=bottoms, color=colors, alpha=0.85, width=0.7)
    ax.axhline(y=0, color=C["dim"], linewidth=0.8)
    labels = [q[:18] + ".." if len(q) > 20 else q for q in sim["question"]]
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=5.5, rotation=55, ha="right")
    ax.set_ylabel("累计盈亏 ($)", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_page(pdf, fig)


def page_trade_table(pdf, df, category, title_label, bankroll=1000.0):
    sub = df if category is None else df[df["category"] == category]
    sim = simulate(sub, "hybrid", bankroll=bankroll)
    if sim.empty:
        return

    rows_per_page = 28
    total_pages = (len(sim) + rows_per_page - 1) // rows_per_page

    for page_num in range(total_pages):
        fig = new_page(pdf)
        fig.suptitle(f"交易明细 — {title_label} (第{page_num + 1}/{total_pages}页)", fontsize=14,
                     color=C["primary"], fontweight="bold", y=0.95)

        ax = fig.add_axes([0.03, 0.03, 0.94, 0.88])
        ax.axis("off")
        ax.set_xlim(0, 11); ax.set_ylim(0, rows_per_page + 2)

        cols = ["#", "市场问题", "方向", "模型", "市场", "边际", "Kelly", "赌注", "盈亏", "资金", "W/L"]
        col_x = [0.1, 0.4, 3.6, 4.2, 4.9, 5.6, 6.2, 6.9, 7.8, 8.8, 9.8]

        y = rows_per_page + 1.2
        for j, (c, x) in enumerate(zip(cols, col_x)):
            ax.text(x, y, c, fontsize=7.5, color=C["dim"], fontweight="bold")
        ax.plot([0, 10.5], [y - 0.3, y - 0.3], color=C["border"], linewidth=0.5)

        start = page_num * rows_per_page
        end = min(start + rows_per_page, len(sim))
        chunk = sim.iloc[start:end]

        for i, (_, r) in enumerate(chunk.iterrows()):
            row_y = rows_per_page - i
            color = C["green"] if r["win"] else C["red"]
            q = r["question"][:25] + ".." if len(r["question"]) > 27 else r["question"]
            vals = [
                str(start + i + 1), q, r["side"],
                f"{r['p']:.1%}", f"{r['mkt']:.1%}", f"{r['edge']:.1%}",
                f"{r['kf']:.1%}", f"${r['bet']:.0f}",
                f"${r['pnl']:+,.0f}", f"${r['bank']:,.0f}",
                "W" if r["win"] else "L",
            ]
            for j, (v, x) in enumerate(zip(vals, col_x)):
                c = color if j in (8, 9, 10) else C["text"]
                ax.text(x, row_y, v, fontsize=7.2, color=c, fontfamily=MONO)
            ax.plot([0, 10.5], [row_y - 0.3, row_y - 0.3], color=C["border"],
                    linewidth=0.2, alpha=0.3)

        save_page(pdf, fig)


def page_conclusions(pdf, df):
    fig = new_page(pdf)
    fig.suptitle("结论与建议", fontsize=20,
                 color=C["primary"], fontweight="bold", y=0.95)

    ax = fig.add_axes([0.06, 0.02, 0.88, 0.88])
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    sim_nc = simulate(df[df["category"] == "非加密货币"], "hybrid")
    s_nc = stats(sim_nc)

    y = 9.8
    sections = [
        ("核心发现", [
            f"1. 非加密货币市场表现出强劲且一致的超额收益：ROI {s_nc['roi']:+.0f}%，",
            f"   胜率 {s_nc['wr']:.0f}%，夏普比 {s_nc['sharpe']:.2f}，共 {s_nc['n']} 笔交易。",
            "",
            "2. 加密货币预测持续跑输市场 — 模型对 BTC/ETH 价格问题的概率估计",
            "   系统性地差于市场隐含概率。胜率仅约 30%。",
            "",
            "3. Half-Kelly (0.5x) 接近最优。全凯利因估计噪声导致过度下注，",
            "   反而亏损。1/4 Kelly (0.25x) 更安全但会放弃可观收益。",
            "",
            "4. 所有 9 种聚合机制在非加密市场均盈利。极端化方法 ROI 最高但波动更大，",
            "   混合（M4）提供最佳的风险调整后表现。",
            "",
            "5. 体育市场（NBA、NHL、CBB、足球）是主要的 Alpha 来源。",
            "   多专家辩论结构能挖掘出单模型和普通玩家忽视的分析边际。",
        ]),
        ("建议", [
            "1. 仅在非加密货币市场部署资金。排除所有加密货币价格预测。",
            "",
            "2. 采用 Half-Kelly (0.5x) 仓位管理搭配混合（M4）聚合器。",
            "",
            "3. 无需设置最小边际过滤 — 凯利公式会自然缩小低信心下注的规模。",
            "   交易所有信号可最大化总盈亏。",
            "",
            "4. 扩大数据采集规模：7 天 48 条预测结果令人鼓舞，但统计上仍不够充分。",
            "   目标 200+ 条已结算预测以达到统计显著性。",
            "",
            "5. 深入调查加密货币失败模式：Agent 可能缺乏实时链上数据和订单流信息，",
            "   而这些信息已被加密市场有效定价。考虑开发专门的加密 Agent 或完全排除加密。",
        ]),
        ("风险提示", [
            "· 小样本（48条预测，7天窗口）— 结果可能无法推广",
            "· 未建模滑点和流动性约束",
            "· 市场经过预过滤（排除了极端价格和地缘政治话题）",
            "· 回测使用记录价格 — 实际执行可能有偏差",
            "· 路径依赖：小样本上的 Kelly 仓位放大了随机性",
            "· 加密货币子样本（n=10）太小，无法得出确定结论，",
            "  但方向性明确",
        ]),
    ]

    for title, lines in sections:
        ax.text(0.2, y, title, fontsize=12, color=C["blue"], fontweight="bold")
        y -= 0.4
        for line in lines:
            if line == "":
                y -= 0.15
                continue
            ax.text(0.3, y, line, fontsize=8.2, color=C["text"])
            y -= 0.28
        y -= 0.3

    save_page(pdf, fig)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成 DePredict 回测 PDF 报告（中文版）")
    parser.add_argument("-o", "--output", default=None, help="输出路径")
    args = parser.parse_args()

    output = Path(args.output) if args.output else PROJECT_ROOT / "reports" / "backtest_report_cn.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)

    print("加载数据...")
    df = load_data()
    n_cr = len(df[df["category"] == "加密货币"])
    n_nc = len(df[df["category"] == "非加密货币"])
    print(f"  {len(df)} 条已结算（{n_nc} 非加密，{n_cr} 加密）")

    print("生成 PDF 报告...")
    with PdfPages(str(output)) as pdf:
        page_cover(pdf, df)
        page_executive_summary(pdf, df)
        page_methodology_1(pdf)
        page_methodology_2(pdf)
        page_methodology_3(pdf)
        page_equity_curve(pdf, df)
        page_mechanism_comparison(pdf, df)
        page_brier_and_edge(pdf, df)
        page_subcategory(pdf, df)
        page_sensitivity(pdf, df)
        page_waterfall(pdf, df, "非加密货币", "非加密货币")
        page_waterfall(pdf, df, "加密货币", "加密货币")
        page_trade_table(pdf, df, "非加密货币", "非加密货币")
        page_trade_table(pdf, df, "加密货币", "加密货币")
        page_conclusions(pdf, df)

    print(f"报告已保存至: {output}")
    print(f"  {output.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
