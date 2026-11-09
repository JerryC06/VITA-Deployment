"""VITA home: two ways to predict from the same FHIR-based ML pipeline.

Run from the repository root:
    python -m streamlit run frontend/web.py
"""

import base64
import json
import sys
from pathlib import Path

import streamlit as st

# Make the repository modules importable when Streamlit runs frontend/web.py.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse Yidan's existing FHIR processing and model code.
from app.fhir_generator import FormError, form_to_bundle  # noqa: E402
from app.model import ModelNotReady, predict_summary  # noqa: E402

ICON_PATH = ROOT / "frontend" / "assets" / "heart-pulse.png"
ICON_URL = "data:image/png;base64," + base64.b64encode(ICON_PATH.read_bytes()).decode("ascii")

st.set_page_config(
    page_title="VITA | Heart Disease Prediction",
    page_icon=str(ICON_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html("""
<style>
.stApp { background: #f5f8fc; }
.block-container { max-width: 1060px; padding-top: 2rem; padding-bottom: 2.5rem; }
[data-testid="stHeader"] {display: none;}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }
.vita-hero {
    background: linear-gradient(115deg, #102c44, #176a82);
    padding: 38px 44px; border-radius: 22px;
    box-shadow: 0 12px 30px rgba(20, 59, 83, .12); margin-bottom: 22px;
}
.vita-brand { display: flex; align-items: center; gap: 16px; margin-bottom: 17px; }
.vita-heart { width: 67px; height: 67px; object-fit: contain; }
.vita-name { color: white; font-weight: 800; font-size: 3.4rem; letter-spacing: .04em; line-height: 1; }
.vita-hero h1 { color: white; font-size: 2.1rem; line-height: 1.2; margin: 0 0 10px; }
.vita-hero p { color: #dcecf2; font-size: 1rem; line-height: 1.6; margin: 0; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #fff; border-radius: 17px; border: 1px solid #dfe8f0;
    box-shadow: 0 5px 18px rgba(23, 54, 79, .04);
}
div.stButton button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background: #116e83; color: white; border-radius: 10px;
    border: none; font-weight: 700; min-height: 47px;
}
div.stButton button[kind="primary"]:disabled,
button[data-testid="stBaseButton-primary"]:disabled {
    background: #dde7ed !important; color: #536777 !important;
    opacity: 1 !important;
}
.vita-caption { color: #687c8c; font-size: .84rem; margin: 18px 0; }
@media(max-width:600px) {
  .vita-hero { padding: 25px; }
  .vita-heart { width: 49px; height: 49px; }
  .vita-name { font-size: 2.7rem; }
  .vita-hero h1 { font-size: 1.65rem; }
}
</style>
""")

st.html(f"""
<div class="vita-hero">
  <div class="vita-brand">
    <img class="vita-heart" src="{ICON_URL}" alt="Heart pulse logo" />
    <span class="vita-name">VITA</span>
  </div>
  <h1>Heart Disease Prediction Model</h1>
  <p>Analyze patient clinical data from FHIR Bundles using machine learning to predict heart disease.</p>
</div>
""")


def predict_and_open_results(bundle: dict, source: str) -> None:
    """Score through Yidan's shared FHIR/model logic and open a full results page."""
    try:
        with st.spinner("Analyzing patient data..."):
            result = predict_summary(bundle)
    except ModelNotReady as exc:
        st.error(str(exc))
        return
    except (ValueError, TypeError, KeyError) as exc:
        st.error(f"Unable to analyze this FHIR Bundle: {exc}")
        return

    st.session_state["vita_result"] = result
    st.session_state["vita_bundle"] = bundle
    st.session_state["vita_source"] = source
    st.switch_page("pages/results.py")


st.subheader("Choose how to enter patient data")

tab_upload, tab_manual = st.tabs(["Upload FHIR Bundle", "Enter Patient Data"])

with tab_upload:
    st.write("Upload a FHIR Bundle in JSON format.")
    with st.container(border=True):
        uploaded_file = st.file_uploader("Choose a FHIR JSON file", type=["json"])
        bundle = None
        if uploaded_file is not None:
            try:
                parsed = json.loads(uploaded_file.getvalue().decode("utf-8"))
                if (
                    isinstance(parsed, dict)
                    and parsed.get("resourceType") == "Bundle"
                    and isinstance(parsed.get("entry"), list)
                ):
                    bundle = parsed
                    st.success(f"File ready: {uploaded_file.name}")
                else:
                    st.error("Expected a FHIR Bundle containing an entry list.")
            except (json.JSONDecodeError, UnicodeDecodeError):
                st.error("This file is not valid UTF-8 JSON.")

        if st.button(
            "Predict Heart Disease", key="predict_upload", type="primary",
            use_container_width=True, disabled=bundle is None,
        ):
            predict_and_open_results(bundle, "Uploaded FHIR Bundle")

    # Optional built-in synthetic example from Yidan's repository.
    sample_path = ROOT / "fhir" / "examples" / "Bundle-vita-0001.json"
    if sample_path.exists():
        st.download_button(
            "Download an example FHIR Bundle",
            data=sample_path.read_bytes(),
            file_name="Bundle-vita-0001.json",
            mime="application/fhir+json",
        )

with tab_manual:
    st.write("Enter the 11 clinical features. VITA will generate a FHIR Bundle before predicting.")
    with st.container(border=True):
        with st.form("manual_patient_form"):
            left, right = st.columns(2, gap="large")
            with left:
                age = st.number_input("Age (years)", min_value=18, max_value=120, value=54)
                sex = st.selectbox("Sex", ["M", "F"], format_func=lambda x: "Male" if x == "M" else "Female")
                chest_pain = st.selectbox("Chest pain type", ["TA", "ATA", "NAP", "ASY"], format_func=lambda x: {
                    "TA": "Typical angina", "ATA": "Atypical angina",
                    "NAP": "Non-anginal pain", "ASY": "Asymptomatic",
                }[x])
                bp = st.number_input(
                    "Resting systolic blood pressure (mmHg)", min_value=0, max_value=300,
                    value=140, help="Enter 0 only when the measurement is missing.",
                )
                cholesterol = st.number_input(
                    "Cholesterol (mg/dL)", min_value=0, max_value=600,
                    value=260, help="Enter 0 only when the measurement is missing.",
                )
                fasting_bs = st.selectbox(
                    "Fasting blood sugar > 120 mg/dL", [0, 1],
                    format_func=lambda x: "Yes" if x == 1 else "No",
                )
            with right:
                resting_ecg = st.selectbox("Resting ECG", ["Normal", "ST", "LVH"])
                max_hr = st.number_input("Maximum heart rate (bpm)", min_value=30, max_value=250, value=150)
                exercise_angina = st.selectbox("Exercise-induced angina", ["N", "Y"], format_func=lambda x: "Yes" if x == "Y" else "No")
                oldpeak = st.number_input("Oldpeak (ST depression)", min_value=-3.0, max_value=7.0, value=2.3, step=0.1, format="%.1f")
                st_slope = st.selectbox("ST slope", ["Up", "Flat", "Down"])

            submitted = st.form_submit_button("Predict Heart Disease", type="primary", use_container_width=True)

    if submitted:
        form_values = {
            "Age": age, "Sex": sex, "ChestPainType": chest_pain,
            "RestingBP": bp, "Cholesterol": cholesterol, "FastingBS": fasting_bs,
            "RestingECG": resting_ecg, "MaxHR": max_hr,
            "ExerciseAngina": exercise_angina, "Oldpeak": oldpeak, "ST_Slope": st_slope,
        }
        try:
            generated_bundle = form_to_bundle(form_values, patient_id="VITA-DEMO-0001")
        except FormError as exc:
            st.error(f"Invalid patient data: {exc}")
        else:
            predict_and_open_results(generated_bundle, "Manual entry")

st.html("""
<div class="vita-caption">
VITA is an educational research prototype for Georgia Tech CS 6440, not a clinically validated diagnostic tool.
Do not use the output for medical decisions.
</div>
""")
