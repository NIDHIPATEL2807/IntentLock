import requests
import streamlit as st

API = "http://localhost:5000"

SCENARIOS = [
    "clean",
    "benign_substitution",
    "f1_prompt_injection",
    "f2_counterfeit_storefront",
    "f3_intent_drift",
    "f4_toctou_protocol",
]

SCENARIO_LABELS = {
    "clean":                    "Clean — normal shopping session",
    "benign_substitution":      "Benign substitution — legitimate swap",
    "f1_prompt_injection":      "F1 — Prompt injection attack",
    "f2_counterfeit_storefront":"F2 — Counterfeit storefront",
    "f3_intent_drift":          "F3 — Intent / decision drift",
    "f4_toctou_protocol":       "F4 — TOCTOU cart tampering",
}

SCENARIO_ICONS = {
    "clean":                    "🟢",
    "benign_substitution":      "🔵",
    "f1_prompt_injection":      "🔴",
    "f2_counterfeit_storefront":"🔴",
    "f3_intent_drift":          "🔴",
    "f4_toctou_protocol":       "🔴",
}

MASTERCARD_NOTE = {
    "clean":                    "A standard payment authorization check would pass this transaction — the spend is within the token cap and the merchant category is authorized. IntentLock agrees: no intent divergence detected.",
    "benign_substitution":      "A standard authorization check would pass this — spend is within cap, category matches. IntentLock also passes it, but for a more specific reason: the substituted item is semantically close to what was requested, not a random swap.",
    "f1_prompt_injection":      "A standard authorization check would pass this transaction — the total spend is within the token cap and the merchant category is authorized. It has no visibility into the injected instruction that caused the agent to add an unauthorized item. IntentLock flagged it by detecting the injected payload and the resulting cart composition divergence.",
    "f2_counterfeit_storefront":"A standard authorization check verifies the merchant ID and spend limit, but does not compare the checkout domain against the merchant the user believed they were shopping with. IntentLock flagged the domain mismatch or spoofed brand signal that the authorization layer cannot see.",
    "f3_intent_drift":          "A standard authorization check would pass this — spend may still be within cap, and the category is technically the same. It cannot detect that the agent autonomously upgraded, duplicated, or changed the item without being asked. IntentLock flagged the semantic and spend divergence from the original stated intent.",
    "f4_toctou_protocol":       "A standard authorization check sees the final cart at checkout time — it has no record of what the cart looked like when the user confirmed it. IntentLock detected that the cart state was tampered with between confirmation and checkout, a class of attack the authorization layer structurally cannot observe.",
}

FEATURE_LABELS = {
    "intent_divergence":         "Intent Divergence",
    "high_risk_sku_ratio":       "High-Risk SKU Ratio",
    "spend_cap_proximity":       "Spend Cap Proximity",
    "graph_entropy":             "Execution Entropy",
    "protocol_consistency":      "Protocol Tamper Flag",
    "injection_density":         "Injection Density",
    "merchant_scope_delta":      "Merchant Scope Delta",
    "structured_intent_mismatch":"Structured Intent Mismatch",
}

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="IntentLock", page_icon="🔒", layout="wide")

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0c0c0c;
    color: #f0f0f0;
}
[data-testid="stSidebar"] { background-color: #111; }

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Typography ── */
h1, h2, h3 { color: #f0f0f0; }

/* ── Cards ── */
.card {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 16px;
}
.card-header {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 12px;
}

/* ── Hero header ── */
.hero {
    background: linear-gradient(135deg, #1a0e00 0%, #0c0c0c 60%);
    border-bottom: 1px solid #2a2a2a;
    padding: 36px 40px 28px;
    margin: -1rem -1rem 32px;
}
.hero-eyebrow {
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #f5a623;
    margin-bottom: 6px;
}
.hero-title {
    font-size: 36px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.1;
    margin: 0;
}
.hero-title span { color: #f5a623; }
.hero-sub {
    font-size: 13px;
    color: #666;
    margin-top: 8px;
}

/* ── Verdict badges ── */
.verdict-allow {
    background: #0a2a1a;
    border: 1.5px solid #1db954;
    border-radius: 10px;
    padding: 20px 24px;
}
.verdict-verify {
    background: #2a1f00;
    border: 1.5px solid #f5a623;
    border-radius: 10px;
    padding: 20px 24px;
}
.verdict-block {
    background: #2a0a0a;
    border: 1.5px solid #eb001b;
    border-radius: 10px;
    padding: 20px 24px;
}
.verdict-label-allow { font-size: 22px; font-weight: 800; color: #1db954; }
.verdict-label-verify { font-size: 22px; font-weight: 800; color: #f5a623; }
.verdict-label-block  { font-size: 22px; font-weight: 800; color: #eb001b; }
.verdict-score { font-size: 13px; color: #888; margin-top: 4px; }

/* ── Risk score ring text ── */
.score-ring {
    font-size: 48px;
    font-weight: 900;
    text-align: center;
    line-height: 1;
}

/* ── Feature bar ── */
.feat-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.feat-name {
    width: 210px;
    font-size: 12px;
    color: #aaa;
    flex-shrink: 0;
}
.feat-bar-bg {
    flex: 1;
    height: 6px;
    background: #2a2a2a;
    border-radius: 4px;
    overflow: hidden;
}
.feat-bar-fill-low  { height: 6px; background: #1db954; border-radius: 4px; }
.feat-bar-fill-mid  { height: 6px; background: #f5a623; border-radius: 4px; }
.feat-bar-fill-high { height: 6px; background: #eb001b; border-radius: 4px; }
.feat-val {
    width: 38px;
    font-size: 12px;
    color: #666;
    text-align: right;
    flex-shrink: 0;
}

/* ── Cart item rows ── */
.cart-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #1e1e1e;
    font-size: 13px;
}
.cart-item:last-child { border-bottom: none; }
.item-type-badge {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 20px;
    background: #2a2a2a;
    color: #888;
}
.item-type-voucher    { background: #3a1a00; color: #f5a623; }
.item-type-subscription { background: #1a003a; color: #a855f7; }
.item-type-addon      { background: #1a2a00; color: #84cc16; }

/* ── Steps ── */
.step-pill {
    display: inline-block;
    background: #1e1e1e;
    border: 1px solid #2a2a2a;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 11px;
    color: #aaa;
    margin: 2px;
}
.step-arrow { color: #444; font-size: 11px; margin: 0 2px; }

/* ── Injection alert ── */
.injection-box {
    background: #1a0800;
    border: 1px solid #7a3500;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 12px;
    color: #f5a623;
    font-family: monospace;
    margin-top: 8px;
}

/* ── Reason pills ── */
.reason-pill {
    display: inline-block;
    background: #2a1000;
    border: 1px solid #7a3500;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 12px;
    color: #f5a623;
    margin: 3px;
}

/* ── Auth note ── */
.auth-note {
    background: #0e0e1a;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 13px;
    color: #9090b0;
    line-height: 1.6;
}

/* ── Selectbox / button overrides ── */
div[data-testid="stSelectbox"] > div > div {
    background-color: #1a1a1a !important;
    border-color: #333 !important;
    color: #f0f0f0 !important;
}
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #f5a623, #eb6d00);
    color: #000;
    font-weight: 800;
    font-size: 14px;
    border: none;
    border-radius: 8px;
    padding: 10px 32px;
    width: 100%;
    letter-spacing: 0.05em;
}
div[data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, #ffc04a, #f5a623);
}
</style>
""", unsafe_allow_html=True)

# ── Hero header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">Mastercard Innovation Challenge · GFF 2026</div>
  <div class="hero-title">Intent<span>Lock</span></div>
  <div class="hero-sub">Agentic Transaction Firewall &nbsp;·&nbsp; All data synthetic &nbsp;·&nbsp; Prototype</div>
</div>
""", unsafe_allow_html=True)

# ── Scenario selector ────────────────────────────────────────────────────────
col_sel, col_btn = st.columns([3, 1])
with col_sel:
    scenario = st.selectbox(
        "Scenario",
        SCENARIOS,
        format_func=lambda s: f"{SCENARIO_ICONS[s]}  {SCENARIO_LABELS[s]}",
        label_visibility="collapsed",
    )
with col_btn:
    run = st.button("▶  Simulate & Score")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

if not run:
    st.markdown("""
    <div class="card" style="text-align:center; padding: 48px; color:#444;">
        Select a scenario above and click <strong style="color:#f5a623">Simulate & Score</strong> to run a session.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── API calls ────────────────────────────────────────────────────────────────
with st.spinner("Generating session trace..."):
    sim_resp = requests.post(f"{API}/simulate", json={"scenario": scenario})
if sim_resp.status_code != 200:
    st.error(f"Simulation error: {sim_resp.text}")
    st.stop()
trace = sim_resp.json()

with st.spinner("Scoring..."):
    score_resp = requests.post(f"{API}/score", json={"trace": trace})
if score_resp.status_code != 200:
    st.error(f"Scoring error: {score_resp.text}")
    st.stop()
result      = score_resp.json()
risk_score  = result["risk_score"]
tier        = result["tier"]
features    = result["features"]
top_reasons = result["top_reasons"]

left, right = st.columns([1, 1], gap="large")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Session trace
# ══════════════════════════════════════════════════════════════════════════════
with left:
    # Intent
    st.markdown(f"""
    <div class="card">
        <div class="card-header">Stated Intent</div>
        <div style="font-size:17px; font-weight:600; color:#fff; margin-bottom:8px;">
            {trace.get('stated_intent', '—')}
        </div>
    """, unsafe_allow_html=True)
    si = trace.get("structured_intent", {})
    st.markdown(f"""
        <div style="font-size:12px; color:#666;">
            category &nbsp;<code style="color:#aaa">{si.get('category')}</code> &nbsp;·&nbsp;
            budget &nbsp;<code style="color:#aaa">${si.get('max_budget')}</code> &nbsp;·&nbsp;
            qty &nbsp;<code style="color:#aaa">{si.get('quantity')}</code>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Cart
    cart_html = '<div class="card"><div class="card-header">Cart</div>'
    total = sum(i["price"] for i in trace.get("cart", []))
    for item in trace.get("cart", []):
        t = item.get("type", "physical")
        badge_cls = f"item-type-{t}" if t in ("voucher", "subscription", "addon") else ""
        cart_html += f"""
        <div class="cart-item">
            <span>{item['name']}</span>
            <span style="display:flex;align-items:center;gap:8px;">
                <span style="color:#f0f0f0;font-weight:600">${item['price']:.2f}</span>
                <span class="item-type-badge {badge_cls}">{t}</span>
            </span>
        </div>"""
    cart_html += f"""
        <div style="text-align:right; margin-top:10px; font-size:12px; color:#666;">
            Total &nbsp;<strong style="color:#f0f0f0">${total:.2f}</strong>
            &nbsp;/&nbsp; cap &nbsp;<strong style="color:#f0f0f0">${trace.get('token_spend_cap', 0)}</strong>
        </div>
    </div>"""
    st.markdown(cart_html, unsafe_allow_html=True)

    # Execution steps
    steps = trace.get("execution_steps", [])
    steps_html = '<div class="card"><div class="card-header">Execution Steps</div><div style="line-height:2.2">'
    for i, s in enumerate(steps):
        steps_html += f'<span class="step-pill">{s}</span>'
        if i < len(steps) - 1:
            steps_html += '<span class="step-arrow">›</span>'
    steps_html += "</div></div>"
    st.markdown(steps_html, unsafe_allow_html=True)

    # Injection (if present)
    injections = trace.get("injected_text_encountered", [])
    if injections:
        inj_html = '<div class="card"><div class="card-header">⚠ Injected Text Encountered</div>'
        for t in injections:
            inj_html += f'<div class="injection-box">{t}</div>'
        inj_html += "</div>"
        st.markdown(inj_html, unsafe_allow_html=True)

    # Attack metadata
    family  = trace.get("attack_family", "—")
    variant = trace.get("attack_variant") or "—"
    st.markdown(f"""
    <div class="card">
        <div class="card-header">Attack Metadata</div>
        <div style="display:flex; gap:32px; font-size:13px;">
            <div><span style="color:#555">Family</span><br>
                 <code style="color:#f5a623">{family}</code></div>
            <div><span style="color:#555">Variant</span><br>
                 <code style="color:#f5a623">{variant}</code></div>
            <div><span style="color:#555">Labelled fraud</span><br>
                 <code style="color:#f5a623">{'Yes' if trace.get('is_fraud') else 'No'}</code></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Verdict
# ══════════════════════════════════════════════════════════════════════════════
with right:

    # Verdict card
    verdict_cls   = f"verdict-{tier}"
    label_cls     = f"verdict-label-{tier}"
    tier_text     = {"allow": "✔  ALLOW", "verify": "⚠  VERIFY", "block": "✖  BLOCK"}[tier]
    tier_color    = {"allow": "#1db954",   "verify": "#f5a623",   "block": "#eb001b"}[tier]

    # Score ring colour
    if risk_score < 30:
        score_color = "#1db954"
    elif risk_score < 70:
        score_color = "#f5a623"
    else:
        score_color = "#eb001b"

    st.markdown(f"""
    <div class="{verdict_cls}" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div>
            <div class="{label_cls}">{tier_text}</div>
            <div class="verdict-score">IntentLock risk assessment</div>
        </div>
        <div class="score-ring" style="color:{score_color};">{risk_score}<span style="font-size:18px;color:#444">/100</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Top reasons / allow caption
    if tier == "allow":
        if top_reasons:
            top_name, top_val = top_reasons[0].split(": ")
            st.markdown(f"""
            <div style="font-size:12px; color:#555; margin-bottom:16px; padding: 10px 14px;
                        background:#111; border-radius:8px; border:1px solid #1e1e1e;">
                No significant risk signals detected. Highest reading:
                <strong style="color:#666">{top_name}</strong> ({top_val}) — within normal range.
            </div>
            """, unsafe_allow_html=True)
    else:
        reasons_html = '<div style="margin-bottom:16px;">'
        reasons_html += '<div style="font-size:11px;color:#666;letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px;">Primary risk signals</div>'
        for r in top_reasons:
            reasons_html += f'<span class="reason-pill">{r}</span>'
        reasons_html += "</div>"
        st.markdown(reasons_html, unsafe_allow_html=True)

    # Feature bars
    st.markdown('<div class="card"><div class="card-header">Feature Readings</div>', unsafe_allow_html=True)
    bars_html = ""
    for name, val in features.items():
        pct = min(val * 100, 100)
        if pct < 30:
            bar_cls = "feat-bar-fill-low"
        elif pct < 70:
            bar_cls = "feat-bar-fill-mid"
        else:
            bar_cls = "feat-bar-fill-high"
        label = FEATURE_LABELS.get(name, name)
        bars_html += f"""
        <div class="feat-row">
            <div class="feat-name">{label}</div>
            <div class="feat-bar-bg"><div class="{bar_cls}" style="width:{pct}%"></div></div>
            <div class="feat-val">{val:.2f}</div>
        </div>"""
    st.markdown(bars_html + "</div>", unsafe_allow_html=True)

    # Auth-layer gap note
    st.markdown(f"""
    <div class="card" style="margin-top:4px;">
        <div class="card-header">What standard payment auth alone would see</div>
        <div class="auth-note">{MASTERCARD_NOTE[scenario]}</div>
    </div>
    """, unsafe_allow_html=True)
