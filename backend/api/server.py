import uuid
from flask import Flask, request, jsonify
from backend.redteam.batch_generator import generate_session_trace
from backend.blueteam.inference import score_session

app = Flask(__name__)

VALID_SCENARIOS = {
    "clean",
    "benign_substitution",
    "f1_prompt_injection",
    "f2_counterfeit_storefront",
    "f3_intent_drift",
    "f4_toctou_protocol",
}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/simulate", methods=["POST"])
def simulate():
    body = request.get_json(force=True)
    scenario = body.get("scenario", "clean")
    if scenario not in VALID_SCENARIOS:
        return jsonify({"error": f"unknown scenario '{scenario}'", "valid": sorted(VALID_SCENARIOS)}), 400
    trace = generate_session_trace(str(uuid.uuid4()), scenario)
    return jsonify(trace)


@app.route("/score", methods=["POST"])
def score():
    body = request.get_json(force=True)
    trace = body.get("trace")
    if not trace:
        return jsonify({"error": "missing 'trace' in request body"}), 400
    return jsonify(score_session(trace))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
