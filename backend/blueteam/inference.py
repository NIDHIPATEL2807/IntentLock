import numpy as np
import joblib
from .feature_extractor import extract_features_from_trace, FEATURE_NAMES

_model = None
_importance_weights = None  # normalised feature importances, cached on first load


def load_model(path="models/intentguard_lgbm.pkl"):
    global _model, _importance_weights
    if _model is None:
        _model = joblib.load(path)
        raw_imp = _model.feature_importance(importance_type="gain")
        total = raw_imp.sum() or 1.0
        _importance_weights = raw_imp / total
    return _model


def score_session(trace: dict, model_path="models/intentguard_lgbm.pkl") -> dict:
    model = load_model(model_path)
    features = extract_features_from_trace(trace)
    raw = float(model.predict(features.reshape(1, -1))[0])
    risk_score = int(raw * 100)
    tier = "allow" if risk_score < 30 else "verify" if risk_score < 70 else "block"
    feature_dict = {name: float(val) for name, val in zip(FEATURE_NAMES, features)}

    # Rank by value × importance, but only for features elevated above a
    # per-feature clean baseline — this stops ubiquitous features like
    # spend_cap_proximity (non-zero in every session) from dominating the
    # display when they aren't the actual discriminating signal.
    CLEAN_BASELINE = {
        "intent_divergence": 0.05,
        "high_risk_sku_ratio": 0.0,
        "spend_cap_proximity": 0.85,   # clean sessions naturally sit ~0.8–0.9
        "graph_entropy": 1.0,          # 3-step clean sessions produce ~1.0
        "protocol_consistency": 0.0,
        "injection_density": 0.0,
        "merchant_scope_delta": 0.0,
        "structured_intent_mismatch": 0.0,
    }
    feature_vals = np.array([feature_dict[n] for n in FEATURE_NAMES], dtype=np.float32)
    excess = np.array(
        [max(0.0, feature_dict[n] - CLEAN_BASELINE[n]) for n in FEATURE_NAMES],
        dtype=np.float32,
    )
    scores = excess * _importance_weights
    ranked_idx = np.argsort(scores)[::-1]
    top_reasons = [
        f"{FEATURE_NAMES[i]}: {feature_vals[i]:.2f}"
        for i in ranked_idx[:2]
        if excess[i] > 0
    ]

    return {
        "risk_score": risk_score,
        "tier": tier,
        "features": feature_dict,
        "top_reasons": top_reasons,
    }
