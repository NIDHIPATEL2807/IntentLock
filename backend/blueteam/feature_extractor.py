import re
from collections import Counter

import numpy as np
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer("all-MiniLM-L6-v2")


def _transition_entropy(steps: list) -> float:
    """Shannon entropy over consecutive tool-call pairs."""
    if len(steps) < 2:
        return 0.0
    transitions = list(zip(steps, steps[1:]))
    counts = Counter(transitions)
    total = sum(counts.values())
    probs = [c / total for c in counts.values()]
    return float(-sum(p * np.log2(p) for p in probs))


def extract_features_from_trace(trace: dict) -> np.ndarray:
    cart = trace.get("cart", [])
    cart_description = " ".join(item["name"] for item in cart) or "Empty Cart"

    emb_intent = embedder.encode(trace["stated_intent"], convert_to_numpy=True)
    emb_cart = embedder.encode(cart_description, convert_to_numpy=True)
    cosine_sim = np.dot(emb_intent, emb_cart) / (
        np.linalg.norm(emb_intent) * np.linalg.norm(emb_cart) + 1e-7
    )
    # f1: how far the cart drifted from what was asked
    f1_intent_divergence = float(1.0 - cosine_sim)

    total_val = sum(item["price"] for item in cart) or 1.0
    voucher_val = sum(
        item["price"]
        for item in cart
        if item.get("type") in ("voucher", "addon", "subscription")
    )
    # f2: fraction of cart value that is non-physical (gift cards, addons, subscriptions)
    f2_sku_ratio = float(voucher_val / total_val)

    # f3: how close total spend is to the cap (>1.0 means over-budget)
    f3_spend_proximity = float(total_val / (trace["token_spend_cap"] or 1.0))

    # f4: real Shannon entropy over tool-call transitions — flat repetition = 0, chaotic = high
    f4_entropy = _transition_entropy(trace.get("execution_steps", []))

    # f5: TOCTOU / protocol tamper flag
    f5_protocol_flag = 1.0 if trace.get("toctou_tampered", False) else 0.0

    injection_keywords = (
        r"(system override|ignore previous|critical|notice|promo"
        r"|updated instructions|mandatory)"
    )
    injections_found = sum(
        len(re.findall(injection_keywords, text, re.IGNORECASE))
        for text in trace.get("injected_text_encountered", [])
    )
    # f6: normalised injection keyword density, capped at 1.0
    f6_injection_density = float(min(injections_found / 2.0, 1.0))

    # f7: did checkout happen at a different domain than the authorised merchant?
    f7_merchant_delta = 1.0 if trace.get("destination_domain_mismatch", False) else 0.0

    # f8: count of non-physical items in cart (gift cards, subscriptions, addons)
    unrequested_items = sum(1 for item in cart if item.get("type") not in ("physical",))
    f8_structured_mismatch = float(min(unrequested_items / 2.0, 1.0))

    return np.array(
        [
            f1_intent_divergence,
            f2_sku_ratio,
            f3_spend_proximity,
            f4_entropy,
            f5_protocol_flag,
            f6_injection_density,
            f7_merchant_delta,
            f8_structured_mismatch,
        ],
        dtype=np.float32,
    )


FEATURE_NAMES = [
    "intent_divergence",
    "high_risk_sku_ratio",
    "spend_cap_proximity",
    "graph_entropy",
    "protocol_consistency",
    "injection_density",
    "merchant_scope_delta",
    "structured_intent_mismatch",
]


if __name__ == "__main__":
    import pandas as pd

    df = pd.read_parquet("backend/data/agentic_fraud_telemetry.parquet")

    families = [
        "clean",
        "benign_substitution",
        "f1_prompt_injection",
        "f2_counterfeit_storefront",
        "f3_intent_drift",
        "f4_toctou_protocol",
    ]

    print(f"{'family':<30} " + "  ".join(f"{n[:8]:>8}" for n in FEATURE_NAMES))
    print("-" * 110)

    for family in families:
        sample = df[df["attack_family"] == family].iloc[0].to_dict()
        feats = extract_features_from_trace(sample)
        variant = sample.get("attack_variant") or "-"
        label = f"{family} ({variant})"
        print(f"{label:<30} " + "  ".join(f"{v:>8.3f}" for v in feats))
