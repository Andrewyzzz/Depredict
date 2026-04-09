"""
Post-aggregation calibration for model predictions.

Implements two complementary techniques validated by the n=143 significance
analysis (see reports/significance_report_cn_n143.pdf):

  1. Combined predictor:  P = α · p_model + (1 − α) · p_market
  2. Clipping toward market: P = clip(P, p_market − δ, p_market + δ)

Both are applied in sequence (combined → clip). Optimal (α, δ) are fit from
historical resolved predictions via Leave-One-Out cross-validation.

Default identity parameters (α=1.0, δ=1.0) leave the model output unchanged,
so it is safe to call `calibrate()` even before `fit_calibration()` has run.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# From backend/app/core/calibration.py: walk up four levels to the project
# root, then into data/prospective/. The same file is consumed by scripts/
# via the project-root copy of this module.
_DEFAULT_PARAMS_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "prospective"
    / "calibration.json"
)


# ── Parameters & application ──────────────────────────────────────


@dataclass
class CalibrationParams:
    """Fitted parameters for the calibration pipeline.

    Identity defaults (α=1, δ=1) make `calibrate()` a no-op, so the system
    behaves like the raw model until `fit_calibration()` has been run.
    """

    alpha: float = 1.0
    delta: float = 1.0
    fitted_at: Optional[str] = None
    n_train: int = 0
    raw_brier: Optional[float] = None
    market_brier: Optional[float] = None
    calibrated_brier: Optional[float] = None
    p_value_vs_market: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationParams":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def is_identity(self) -> bool:
        return self.alpha >= 0.999 and self.delta >= 0.999


def calibrate(p_model: float, p_market: float, params: CalibrationParams) -> float:
    """Apply (combined predictor → clipping) to a single probability.

    Args:
        p_model: Raw model probability in [0, 1].
        p_market: Market price in [0, 1].
        params: Fitted calibration parameters.

    Returns:
        Calibrated probability in [0, 1].
    """
    pm = float(p_model)
    mk = float(p_market)
    blend = params.alpha * pm + (1.0 - params.alpha) * mk
    clipped = max(mk - params.delta, min(mk + params.delta, blend))
    return float(min(1.0, max(0.0, clipped)))


def load_params(path: Optional[Path] = None) -> CalibrationParams:
    """Load calibration parameters from disk; return identity defaults if absent."""
    p = Path(path) if path else _DEFAULT_PARAMS_PATH
    if not p.exists():
        logger.info("No calibration file at %s; using identity params", p)
        return CalibrationParams()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return CalibrationParams.from_dict(json.load(f))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load calibration from %s: %s", p, e)
        return CalibrationParams()


def save_params(params: CalibrationParams, path: Optional[Path] = None) -> None:
    """Atomically save calibration parameters to disk."""
    p = Path(path) if path else _DEFAULT_PARAMS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(params.to_dict(), f, indent=2)
    tmp.replace(p)


# ── Fitting (Leave-One-Out CV) ────────────────────────────────────


@dataclass
class FitResult:
    params: CalibrationParams
    raw_brier: float
    market_brier: float
    calibrated_brier: float
    p_value: float
    n: int
    alpha_per_fold: list[float] = field(default_factory=list)
    delta_per_fold: list[float] = field(default_factory=list)


def _ttest_one_sided_less(a: np.ndarray, b: np.ndarray) -> float:
    """One-sided paired t-test for H1: mean(a) < mean(b)."""
    from scipy import stats

    t, tp = stats.ttest_rel(a, b)
    return float(tp / 2.0 if t < 0 else 1.0 - tp / 2.0)


def fit_calibration(
    model: np.ndarray,
    market: np.ndarray,
    outcomes: np.ndarray,
    alpha_grid: Optional[np.ndarray] = None,
    delta_grid: Optional[np.ndarray] = None,
) -> FitResult:
    """Fit (α, δ) jointly via Leave-One-Out cross-validation.

    For each held-out sample, we grid-search the (α, δ) combination that
    minimizes Brier on the remaining n−1 samples, then evaluate the held-out
    point with those parameters. The reported parameters are the median across
    folds — a stable estimate even when individual folds disagree.

    Args:
        model:    Raw model probabilities, shape (n,) in [0, 1].
        market:   Market prices, shape (n,) in [0, 1].
        outcomes: Binary outcomes, shape (n,) in {0, 1}.

    Returns:
        FitResult with the modal (α, δ), out-of-sample Brier, and one-sided
        p-value of the calibrated predictor versus market.

    Raises:
        ValueError: If fewer than 5 samples are provided.
    """
    n = len(model)
    if n < 5:
        raise ValueError(f"need at least 5 samples to fit, got {n}")

    if alpha_grid is None:
        alpha_grid = np.arange(0.0, 1.01, 0.05)
    if delta_grid is None:
        delta_grid = np.arange(0.02, 0.30, 0.02)

    model = np.asarray(model, dtype=float)
    market = np.asarray(market, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)

    market_err = (market - outcomes) ** 2
    raw_err = (model - outcomes) ** 2

    loo_errors = np.zeros(n)
    alpha_folds: list[float] = []
    delta_folds: list[float] = []

    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        m_tr, mk_tr, o_tr = model[mask], market[mask], outcomes[mask]

        best_b = np.inf
        best_alpha, best_delta = 1.0, 1.0
        for a in alpha_grid:
            blend = a * m_tr + (1.0 - a) * mk_tr
            for d in delta_grid:
                pred = np.clip(blend, mk_tr - d, mk_tr + d)
                b = float(np.mean((pred - o_tr) ** 2))
                if b < best_b:
                    best_b = b
                    best_alpha, best_delta = float(a), float(d)

        blend_i = best_alpha * model[i] + (1.0 - best_alpha) * market[i]
        pred_i = float(np.clip(blend_i, market[i] - best_delta, market[i] + best_delta))
        loo_errors[i] = (pred_i - outcomes[i]) ** 2
        alpha_folds.append(best_alpha)
        delta_folds.append(best_delta)

    alpha_mode = float(np.median(alpha_folds))
    delta_mode = float(np.median(delta_folds))

    raw_brier = float(np.mean(raw_err))
    market_brier = float(np.mean(market_err))
    cal_brier = float(np.mean(loo_errors))
    p_value = _ttest_one_sided_less(loo_errors, market_err)

    params = CalibrationParams(
        alpha=alpha_mode,
        delta=delta_mode,
        fitted_at=datetime.now(timezone.utc).isoformat(),
        n_train=n,
        raw_brier=raw_brier,
        market_brier=market_brier,
        calibrated_brier=cal_brier,
        p_value_vs_market=p_value,
    )

    return FitResult(
        params=params,
        raw_brier=raw_brier,
        market_brier=market_brier,
        calibrated_brier=cal_brier,
        p_value=p_value,
        n=n,
        alpha_per_fold=alpha_folds,
        delta_per_fold=delta_folds,
    )
