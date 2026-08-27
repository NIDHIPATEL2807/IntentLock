import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

from .feature_extractor import extract_features_from_trace, FEATURE_NAMES


def train():
    df = pd.read_parquet("backend/data/agentic_fraud_telemetry.parquet").reset_index(drop=True)

    X = np.array([extract_features_from_trace(row.to_dict()) for _, row in df.iterrows()])
    y = df["is_fraud"].values

    # Keep attack_family aligned so we can report per-family detection rates after splitting
    idx_train, idx_test = train_test_split(
        np.arange(len(df)), test_size=0.2, random_state=42, stratify=y
    )
    X_train, X_test = X[idx_train], X[idx_test]
    y_train, y_test = y[idx_train], y[idx_test]
    families_test = df["attack_family"].iloc[idx_test].values
    variants_test = df["attack_variant"].iloc[idx_test].values

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_NAMES)
    val_data = lgb.Dataset(X_test, label=y_test, reference=train_data, feature_name=FEATURE_NAMES)

    params = {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.9,
        "verbose": -1,
    }
    model = lgb.train(
        params, train_data, num_boost_round=150, valid_sets=[train_data, val_data]
    )

    preds_prob = model.predict(X_test, num_iteration=model.best_iteration)
    preds_binary = (preds_prob >= 0.5).astype(int)

    # 1. ROC-AUC
    auc = roc_auc_score(y_test, preds_prob)
    print(f"\nROC-AUC: {auc:.4f}")
    if auc > 0.995:
        print("  [note] AUC near 1.0 — check for feature leakage before trusting this number")

    # 2. Overall classification report
    print("\n" + classification_report(y_test, preds_binary, target_names=["Legitimate", "Fraud"]))

    # 3. FPR broken out by family — clean and benign_substitution are the key ones
    cm_all = confusion_matrix(y_test, preds_binary)
    overall_fpr = cm_all[0][1] / (cm_all[0][0] + cm_all[0][1] + 1e-9)
    print(f"Overall False Positive Rate (legit flagged as fraud): {overall_fpr * 100:.2f}%\n")

    print("FPR by legitimate family:")
    for fam in ("clean", "benign_substitution"):
        mask = families_test == fam
        if mask.sum() == 0:
            continue
        fp = ((preds_binary[mask] == 1) & (y_test[mask] == 0)).sum()
        total = (y_test[mask] == 0).sum()
        print(f"  {fam:<25} FPR = {fp}/{total} = {fp/max(total,1)*100:.1f}%")

    # 4. Detection rate (recall) per fraud family and per variant
    print("\nDetection rate by fraud family:")
    for fam in ("f1_prompt_injection", "f2_counterfeit_storefront", "f3_intent_drift", "f4_toctou_protocol"):
        mask = (families_test == fam) & (y_test == 1)
        if mask.sum() == 0:
            continue
        caught = preds_binary[mask].sum()
        total = mask.sum()
        print(f"  {fam:<30} {caught}/{total} = {caught/total*100:.1f}%")

    print("\nDetection rate by attack variant (fraud sessions only):")
    fraud_mask = y_test == 1
    unique_variants = [v for v in np.unique(variants_test[fraud_mask]) if v is not None and str(v) != "nan"]
    variant_results = []
    for variant in unique_variants:
        mask = (variants_test == variant) & fraud_mask
        if mask.sum() < 5:
            continue
        caught = preds_binary[mask].sum()
        total = mask.sum()
        variant_results.append((variant, caught, total, caught / total * 100))
    for variant, caught, total, rate in sorted(variant_results, key=lambda x: x[3]):
        print(f"  {variant:<30} {caught}/{total} = {rate:.1f}%")

    joblib.dump(model, "models/intentguard_lgbm.pkl")
    print("\nSaved -> models/intentguard_lgbm.pkl")


if __name__ == "__main__":
    train()
