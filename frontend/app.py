"""FinGuard-AI — Streamlit dashboard (talks to FastAPI backend)."""
import os
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="FinGuard-AI", page_icon="🛡️", layout="wide")


# ─────────────────────────── API helpers ───────────────────────────
def _call(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{API_URL}{path}", timeout=5, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.session_state["api_error"] = str(e)
        return None


def api_get(path: str, params: dict | None = None):
    return _call("GET", path, params=params)


def api_post(path: str, payload: dict):
    return _call("POST", path, json=payload)


# ─────────────────────────── Sidebar ───────────────────────────
with st.sidebar:
    st.title("🛡️ FinGuard-AI")
    st.caption("Real-time Fraud Detection")
    health = api_get("/health")
    if health and health.get("status") == "ok":
        st.success(f"API online · model: `{health.get('model')}`")
    else:
        st.error("API offline — start FastAPI backend")
    page = st.radio("Navigate", ["📊 Dashboard", "🔍 Score Transaction",
                                 "📜 Transactions", "🚨 Alerts", "🔬 Drift Check"])
    st.divider()
    st.caption(f"API: {API_URL}")


# ─────────────────────────── Dashboard ───────────────────────────
def dashboard():
    st.header("📊 Live Fraud Overview")
    txns = api_get("/transactions", {"limit": 500}) or []
    if not txns:
        st.info("No transactions yet. Start the Kafka producer or score one manually.")
        return

    df = pd.DataFrame(txns)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Txns", len(df))
    fraud_n = int(df["is_fraud"].sum())
    c2.metric("Fraud Flagged", fraud_n)
    c3.metric("Fraud Rate", f"{fraud_n / len(df):.1%}")
    c4.metric("Avg Fraud Prob", f"{df['fraud_prob'].mean():.2f}")

    left, right = st.columns(2)
    with left:
        st.subheader("Fraud probability distribution")
        fig = px.histogram(df, x="fraud_prob", nbins=30, color="is_fraud",
                           color_discrete_map={True: "#ef4444", False: "#22c55e"})
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Fraud by merchant category")
        agg = (df[df["is_fraud"]].groupby("merchant_category")
               .size().reset_index(name="count"))
        if not agg.empty:
            st.plotly_chart(px.bar(agg, x="merchant_category", y="count",
                                   color="count"), use_container_width=True)
        else:
            st.write("No fraud yet.")


# ─────────────────────────── Manual scoring ───────────────────────────
def score_page():
    st.header("🔍 Score a Transaction")
    st.caption("Spend average and recent activity are pulled from the user's "
               "real history, not this form — so a fraudster can't just claim "
               "a clean record.")
    with st.form("score_form"):
        c1, c2 = st.columns(2)
        with c1:
            user_id = st.text_input("User ID", "user_1")
            amount = st.number_input("Amount", 1.0, 100000.0, 500.0)
            # keep these options in sync with CATEGORIES in src/ml/features.py —
            # frontend talks to the API over HTTP only, no shared import
            merchant = st.selectbox("Merchant category",
                ["grocery", "electronics", "travel", "gambling", "crypto", "food"])
        with c2:
            device = st.selectbox("Device type", ["ios", "android", "web"])
            country = st.selectbox("Country", ["IN", "US", "GB", "NG", "RU"])
        submitted = st.form_submit_button("Score", use_container_width=True)

    if submitted:
        payload = {
            "transaction_id": f"ui-{int(time.time())}",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "amount": amount, "merchant_category": merchant,
            "device_type": device, "country": country,
        }
        res = api_post("/score", payload)
        if res:
            prob = res["fraud_probability"]
            st.metric("Fraud probability", f"{prob:.2%}")
            st.progress(min(prob, 1.0))
            if res["is_fraud"]:
                st.error(f"🚨 FRAUD DETECTED · model: {res['model']}")
            else:
                st.success(f"✅ Legitimate · model: {res['model']}")


def _format_transactions(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    display["amount"] = display["amount"].map(lambda x: f"{x:,.2f}")
    display["fraud_prob"] = display["fraud_prob"].map(lambda x: f"{x:.2%}")
    display["is_fraud"] = display["is_fraud"].map(lambda x: "Yes" if x else "No")
    return display


def _render_transactions_table(df: pd.DataFrame) -> None:
    display = _format_transactions(df)
    st.markdown(
        display.to_html(index=False, border=0),
        unsafe_allow_html=True,
    )


# ─────────────────────────── Transactions table ───────────────────────────
def transactions_page():
    st.header("📜 Recent Transactions")
    fraud_only = st.toggle("Show fraud only")
    limit = st.slider("Rows", 10, 500, 100)
    txns = api_get("/transactions", {"limit": limit, "fraud_only": fraud_only})
    if txns:
        df = pd.DataFrame(txns)[
            ["transaction_id", "amount", "merchant_category", "country",
             "fraud_prob", "is_fraud", "model_name", "created_at"]]
        _render_transactions_table(df)
    else:
        st.info("No transactions found.")


# ─────────────────────────── Alerts ───────────────────────────
def alerts_page():
    st.header("🚨 Open Fraud Alerts")
    alerts = api_get("/alerts", {"limit": 100})
    if not alerts:
        st.success("No open alerts 🎉")
        return
    for a in alerts:
        color = "🔴" if a["severity"] == "HIGH" else "🟠"
        with st.expander(f"{color} {a['transaction_id']} · "
                         f"{a['severity']} · {a['fraud_prob']:.2%}"):
            st.json(a)
            if st.button("Mark reviewed", key=f"rev-{a['id']}"):
                api_post(f"/alerts/{a['id']}/review", {})
                st.rerun()


# ─────────────────────────── Drift check ───────────────────────────
def drift_page():
    st.header("🔬 Data Drift Check")
    st.caption("Compares recent live traffic against the training reference "
               "set using Evidently. Flags it before a shifted data "
               "distribution starts costing missed fraud.")
    limit = st.slider("Recent transactions to check", 100, 5000, 1000, step=100)
    if st.button("Run drift check", use_container_width=True):
        with st.spinner("Comparing recent traffic to training reference..."):
            res = api_post(f"/drift/check?limit={limit}", {})
        if res:
            c1, c2 = st.columns(2)
            c1.metric("Dataset drift detected", "Yes ⚠️" if res["dataset_drift"] else "No ✅")
            c2.metric("Drifted columns", f"{res['drifted_share']:.1%}")
            if res["dataset_drift"]:
                st.warning("Drift detected — consider retraining "
                          "(`python src/ml/train.py`) on fresher data.")
            else:
                st.success("No significant drift — model is still aligned "
                          "with current traffic.")
            st.caption("Full HTML report saved to `artifacts/drift_report.html`.")


# ─────────────────────────── Router ───────────────────────────
{
    "📊 Dashboard": dashboard,
    "🔍 Score Transaction": score_page,
    "📜 Transactions": transactions_page,
    "🚨 Alerts": alerts_page,
    "🔬 Drift Check": drift_page,
}[page]()

if err := st.session_state.pop("api_error", None):
    st.toast(f"API error: {err}", icon="⚠️")