"""VITA full-page prediction results. Opened from frontend/web.py."""

import base64
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
ICON_PATH = ROOT / "frontend" / "assets" / "heart-pulse.png"
ICON_URL = "data:image/png;base64," + base64.b64encode(ICON_PATH.read_bytes()).decode("ascii")

st.set_page_config(
    page_title="Prediction Results | VITA",
    page_icon=str(ICON_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html("""
<style>
.stApp { background: #f5f8fc; }
.block-container { max-width: 1060px; padding-top: 2rem; padding-bottom: 2.5rem; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }
.vita-head {
    background: linear-gradient(115deg, #102c44, #176a82);
    padding: 26px 34px; border-radius: 19px; margin: 6px 0 26px;
    display: flex; gap: 15px; align-items: center;
}
.vita-heart { width: 52px; height: 52px; object-fit: contain; }
.vita-name { font-size: 2.4rem; color: white; font-weight: 800; letter-spacing: .04em; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: white; border: 1px solid #dfe8f0;
    border-radius: 16px; box-shadow: 0 5px 18px rgba(23,54,79,.04);
}
.vita-note { color: #667a8b; font-size: .86rem; margin-top: 20px; }
</style>
""")

st.html(f"""
<div class="vita-head">
    <img class="vita-heart" src="{ICON_URL}" alt="Heart pulse logo" />
    <span class="vita-name">VITA</span>
</div>
""")

if st.button("← Back to Upload / Patient Entry"):
    st.switch_page("web.py")

result = st.session_state.get("vita_result")
bundle = st.session_state.get("vita_bundle")
source = st.session_state.get("vita_source", "")

if not result or not bundle:
    st.warning("No prediction is available. Upload a FHIR Bundle or enter patient data first.")
    st.stop()

probability = float(result["probability"])
label = int(result["label"])
threshold = float(result["threshold"])
features = result["features"]

st.title("Prediction Results")
st.caption(f"Input method: {source} · Model: Logistic Regression")

with st.container(border=True):
    st.subheader("Prediction summary")
    if label == 1:
        st.warning("Model classification: Positive (Class 1)")
    else:
        st.success("Model classification: Negative (Class 0)")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Estimated probability of Class 1", f"{probability:.2%}")
    with col2:
        st.metric("Classification threshold", f"{threshold:.0%}")

    st.progress(max(0, min(100, round(probability * 100))))
    st.caption(
        "This is an uncalibrated model estimate for this dataset, not a verified "
        "patient-specific clinical risk or a medical diagnosis."
    )

with st.container(border=True):
    st.subheader("Patient clinical features")
    rows = [
        {
            "Feature": field,
            "Value": "Missing (model imputation)" if value is None else str(value),
        }
        for field, value in features.items()
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)


st.html("""
<div class="vita-note">
Educational demonstration for Georgia Tech CS 6440 only. VITA is not intended for clinical diagnosis or treatment decisions.
</div>
""")
