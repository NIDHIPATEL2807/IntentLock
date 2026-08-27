import uuid
import random
import pandas as pd
from .attacks import F1_VARIANTS, F2_VARIANTS, F3_VARIANTS, F4_VARIANTS

BASE_INTENTS = [
    {
        "intent": "Buy a mechanical keyboard under $100", "budget": 100, "category": "electronics",
        "subs": [
            {"substituted": "Mechanical Keyboard TKL Layout under $100", "reason": "out_of_stock"},
            {"substituted": "Mechanical Keyboard Compact 65% Layout", "reason": "better_rated_alt"},
            {"substituted": "Mechanical Keyboard Cherry MX Red switches", "reason": "better_rated_alt"},
        ],
    },
    {
        "intent": "Order organic running socks in size L", "budget": 30, "category": "apparel",
        "subs": [
            {"substituted": "Running Socks Merino Wool Size L", "reason": "better_rated_alt"},
            {"substituted": "Compression Running Socks Size L 2-pack", "reason": "inventory_split"},
            {"substituted": "Athletic Running Socks Size L 3-pack", "reason": "out_of_stock"},
        ],
    },
    {
        "intent": "Purchase cold brew coffee beans 1kg", "budget": 40, "category": "grocery",
        "subs": [
            {"substituted": "Cold Brew Coffee Beans 500g x2", "reason": "inventory_split"},
            {"substituted": "Organic Cold Brew Coffee Beans 1kg Dark Roast", "reason": "better_rated_alt"},
            {"substituted": "Cold Brew Coffee Beans 1kg Single Origin", "reason": "out_of_stock"},
        ],
    },
    {
        "intent": "Get a USB-C hub with 4 ports under $50", "budget": 50, "category": "electronics",
        "subs": [
            {"substituted": "USB-C Hub 7-port (Better Rating)", "reason": "better_rated_alt"},
            {"substituted": "USB-C Hub 4-port Slim Design", "reason": "out_of_stock"},
            {"substituted": "USB-C Hub 4-port with HDMI", "reason": "better_rated_alt"},
        ],
    },
    {
        "intent": "Buy a yoga mat under $35", "budget": 35, "category": "sports",
        "subs": [
            {"substituted": "Yoga Mat Non-Slip 6mm Thickness", "reason": "better_rated_alt"},
            {"substituted": "Yoga Mat Eco-Friendly Cork", "reason": "out_of_stock"},
            {"substituted": "Yoga Mat + Carry Strap Bundle", "reason": "inventory_split"},
        ],
    },
    {
        "intent": "Order a notebook journal pack of 3", "budget": 25, "category": "stationery",
        "subs": [
            {"substituted": "Dotted Journal Notebook Pack of 3", "reason": "out_of_stock"},
            {"substituted": "Hardcover Lined Notebook Pack of 3", "reason": "better_rated_alt"},
            {"substituted": "Notebook Journal Pack of 2 + Pen", "reason": "inventory_split"},
        ],
    },
    {
        "intent": "Find running shoes under $90", "budget": 90, "category": "apparel",
        "subs": [
            {"substituted": "Running Shoes Adidas Ultraboost $89", "reason": "out_of_stock"},
            {"substituted": "Running Shoes Nike React $88", "reason": "better_rated_alt"},
            {"substituted": "Trail Running Shoes under $90", "reason": "better_rated_alt"},
        ],
    },
    {
        "intent": "Purchase a phone case for iPhone 15", "budget": 20, "category": "electronics",
        "subs": [
            {"substituted": "iPhone 15 Case MagSafe Compatible", "reason": "better_rated_alt"},
            {"substituted": "iPhone 15 Slim Phone Case Clear", "reason": "out_of_stock"},
            {"substituted": "iPhone 15 Case + Screen Protector Bundle", "reason": "inventory_split"},
        ],
    },
]

PHASE1_DISTRIBUTIONS = [
    ("clean", 700),
    ("benign_substitution", 300),
    ("f1_prompt_injection", 350),
    ("f2_counterfeit_storefront", 300),
    ("f3_intent_drift", 250),
    ("f4_toctou_protocol", 200),
]

FULL_DISTRIBUTIONS = [
    ("clean", 3800),
    ("benign_substitution", 2000),
    ("f1_prompt_injection", 1100),
    ("f2_counterfeit_storefront", 850),
    ("f3_intent_drift", 850),
    ("f4_toctou_protocol", 600),
]


def generate_session_trace(session_id: str, attack_family: str) -> dict:
    selected = random.choice(BASE_INTENTS)
    trace = {
        "session_id": session_id,
        "stated_intent": selected["intent"],
        "structured_intent": {"category": selected["category"], "max_budget": selected["budget"], "quantity": 1},
        "token_spend_cap": selected["budget"],
        "authorized_category": selected["category"],
        "attack_family": attack_family,
        "attack_variant": None,
        "is_fraud": 0 if attack_family in ("clean", "benign_substitution") else 1,
        "execution_steps": ["search_products", "add_to_cart", "checkout"],
        "cart": [],
        "toctou_tampered": False,
        "injected_text_encountered": [],
        "destination_domain_mismatch": False,
    }

    if attack_family == "clean":
        variation = random.choice(["exact", "cheaper_choice", "extra_search"])
        trace["cart"].append({
            "name": selected["intent"],
            "price": selected["budget"] * random.uniform(0.75, 0.95),
            "type": "physical",
        })
        if variation == "extra_search":
            trace["execution_steps"].insert(1, "search_products")

    elif attack_family == "benign_substitution":
        sub = random.choice(selected["subs"])
        trace["attack_variant"] = sub["reason"]
        trace["cart"].append({
            "name": sub["substituted"],
            "price": selected["budget"] * random.uniform(0.85, 0.95),
            "type": "physical",
        })
        trace["execution_steps"].append("substitute_item")

    elif attack_family == "f1_prompt_injection":
        variant_name, v = random.choice(list(F1_VARIANTS.items()))
        trace["attack_variant"] = variant_name
        trace["cart"].append({
            "name": selected["intent"],
            "price": selected["budget"] * (1 - v["price_ratio"]),
            "type": "physical",
        })
        trace["injected_text_encountered"].append(v["payload"])
        if variant_name != "no_effect":
            trace["cart"].append({
                "name": v["item"],
                "price": selected["budget"] * v["price_ratio"],
                "type": v["type"],
            })
            trace["execution_steps"].append("add_to_cart")
        else:
            trace["is_fraud"] = 0  # injection present, agent resisted — legitimately clean

    elif attack_family == "f2_counterfeit_storefront":
        variant_name, v = random.choice(list(F2_VARIANTS.items()))
        trace["attack_variant"] = variant_name
        trace["cart"].append({
            "name": selected["intent"] + f" (via {v['spoofed_brand']})",
            "price": selected["budget"] * 0.7,
            "type": "physical",
        })
        trace["destination_domain_mismatch"] = v["mismatch_severity"] >= 0.6

    elif attack_family == "f3_intent_drift":
        variant_name, v = random.choice(list(F3_VARIANTS.items()))
        trace["attack_variant"] = variant_name
        trace["cart"].append({
            "name": v["desc"],
            "price": selected["budget"] * v["price_ratio"],
            "type": "physical",
        })
        trace["execution_steps"].append("recommend_upsell")

    elif attack_family == "f4_toctou_protocol":
        variant_name = random.choice(list(F4_VARIANTS.keys()))
        trace["attack_variant"] = variant_name
        trace["cart"].append({
            "name": selected["intent"],
            "price": selected["budget"] * 0.8,
            "type": "physical",
        })
        trace["toctou_tampered"] = True
        trace["execution_steps"].append("recheck_cart_state")

    return trace


def generate_dataset(distributions):
    records = []
    for family, count in distributions:
        for _ in range(count):
            records.append(generate_session_trace(str(uuid.uuid4()), family))
    return pd.DataFrame(records)


def generate_full_dataset(phase1_only: bool = False):
    distributions = PHASE1_DISTRIBUTIONS if phase1_only else FULL_DISTRIBUTIONS
    df = generate_dataset(distributions)
    out_path = "backend/data/agentic_fraud_telemetry.parquet"
    df.to_parquet(out_path)
    print(f"Generated {len(df)} labeled traces -> {out_path}")
    print("\nFamily distribution:")
    print(df["attack_family"].value_counts().to_string())
    print("\nVariant distribution (fraud sessions only):")
    print(df[df["attack_variant"].notna()]["attack_variant"].value_counts().to_string())
    fraud_rate = df["is_fraud"].mean() * 100
    print(f"\nFraud rate: {fraud_rate:.1f}%  |  Clean/benign: {100 - fraud_rate:.1f}%")
    f1_no_effect = df[(df["attack_family"] == "f1_prompt_injection") & (df["is_fraud"] == 0)]
    print(f"\nF1 'no_effect' rows (injection resisted, is_fraud=0): {len(f1_no_effect)}")


if __name__ == "__main__":
    generate_full_dataset(phase1_only=False)
