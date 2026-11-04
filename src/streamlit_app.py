"""
================================================================
STREAMLIT WEB INTERFACE — Underwriting Triage Agent
================================================================

A simple web app so an underwriter (or interviewer) can paste a broker
submission and see the agent's recommendation, reason, risk level, and the
rules it used.

Run on the server:
    streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0

Then open:  http://<server-ip>:8501
"""

import sys
import os

# make the src/ modules importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from pipeline import run_pipeline


# ============================================================
# PAGE SETUP
# ============================================================
st.set_page_config(page_title="Underwriting Triage Agent", page_icon="📋")

st.title("🏢 SME Property Underwriting Triage Agent")
st.caption(
    "Paste a broker submission. The agent checks it against the underwriting "
    "rules and recommends QUOTE / DECLINE / REFER for an underwriter to approve. "
    "It never makes the final decision."
)

# a sample to help the user
EXAMPLE = (
    "Business: Bakery, Leeds. Cover wanted: property, sum insured 450000 GBP. "
    "Building constructed 1998. Claims history: no claims in past 5 years. "
    "Fire protection: fire alarm and sprinkler system installed."
)


# ============================================================
# INPUT
# ============================================================
submission = st.text_area(
    "Broker submission",
    value=EXAMPLE,
    height=160,
)

if st.button("Assess submission", type="primary"):
    with st.spinner("Assessing against underwriting rules..."):
        result = run_pipeline(submission)

    # ---- headline decision ----
    decision = result["decision"]
    colour = {"QUOTE": "green", "DECLINE": "red", "REFER": "orange"}.get(decision, "gray")
    st.markdown(f"### Recommendation: :{colour}[{decision}]")

    if result.get("risk_level"):
        st.write(f"**Risk level:** {result['risk_level']}")
    st.write(f"**Reason:** {result.get('reason')}")

    # ---- the rules it used (transparency) ----
    rules = result.get("rules_used", [])
    if rules:
        with st.expander("Rules retrieved (why it decided this)"):
            for r in rules:
                st.write(f"- **{r['section']}** ({r['source']}) — similarity {r['similarity']}")

    # ---- a reminder of the human-in-the-loop principle ----
    st.info("This is a recommendation only. A human underwriter approves or overrides the final decision.")
