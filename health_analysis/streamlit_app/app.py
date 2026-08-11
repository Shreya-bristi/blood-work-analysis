import os
import base64
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from langchain_google_genai import ChatGoogleGenerativeAI
from pypdf import PdfReader


# Local development: loads GOOGLE_API_KEY from .env
load_dotenv()


# Deployment: use Streamlit Secrets if available
try:
    if "GOOGLE_API_KEY" in st.secrets:
        os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    # No Streamlit secrets file locally — that's fine
    pass


# Make sure the key exists
if not os.getenv("GOOGLE_API_KEY"):
    st.error("GOOGLE_API_KEY is not configured.")
    st.stop()


st.set_page_config(
    page_title="Blood Work Analyzer",
    layout="wide"
)


def set_background():
    image_path = Path(__file__).parent.parent / "img.png"

    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode()

    st.markdown(
        f"""
        <style>

        .stApp {{
            background-image:
                linear-gradient(
                    rgba(5, 12, 28, 0.25),
                    rgba(5, 12, 28, 0.25)
                ),
                url("data:image/png;base64,{encoded}");

            background-size: cover;
            background-position: center top;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        [data-testid="stAppViewContainer"] {{
            background: transparent;
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )


set_background()


BOX_STYLE = (
    "height:230px; overflow-y:auto; "
    "background-color:rgba(20, 20, 20, 0.92); "
    "border:1px solid rgba(255,255,255,0.15); "
    "border-radius:8px; padding:14px; "
    "color:#f0f0f0; font-size:0.9rem; line-height:1.5;"
)


PDF_CHAR_MAP = {
    "–": "-",
    "—": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "•": "-",
    "…": "...",
}


@st.cache_resource
def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.6-flash"
    )


def to_html(text: str) -> str:
    text = text.strip()
    text = text.replace("**", "")
    return text.replace("\n", "<br>")


def render_box(title: str, content: str):
    st.markdown(f"**{title}**")

    st.markdown(
        f'<div style="{BOX_STYLE}">{to_html(content)}</div>',
        unsafe_allow_html=True,
    )


def extract_text_from_upload(uploaded_file) -> str:
    if uploaded_file.name.lower().endswith(".pdf"):

        reader = PdfReader(uploaded_file)

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    return uploaded_file.read().decode(
        "utf-8",
        errors="ignore"
    )


def handle_upload():
    uploaded_file = st.session_state.get("uploaded_file")

    if uploaded_file is None:
        return

    st.session_state.blood_report_text = (
        extract_text_from_upload(uploaded_file)
    )


def sanitize_for_pdf(text: str) -> str:
    for src, dest in PDF_CHAR_MAP.items():
        text = text.replace(src, dest)

    return (
        text
        .encode("latin-1", "ignore")
        .decode("latin-1")
    )


def build_analysis_pdf(
    summary: str,
    diet: str
) -> bytes:

    pdf = FPDF()

    pdf.add_page()

    pdf.set_font(
        "Helvetica",
        "B",
        16
    )

    pdf.cell(
        0,
        10,
        "Blood Work Analysis",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.ln(4)

    pdf.set_font(
        "Helvetica",
        "B",
        13
    )

    pdf.cell(
        0,
        8,
        "Health Summary",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_font(
        "Helvetica",
        "",
        11
    )

    pdf.multi_cell(
        0,
        6,
        sanitize_for_pdf(summary)
    )

    pdf.ln(6)

    pdf.set_font(
        "Helvetica",
        "B",
        13
    )

    pdf.cell(
        0,
        8,
        "Suggested Diet Plan",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_font(
        "Helvetica",
        "",
        11
    )

    pdf.multi_cell(
        0,
        6,
        sanitize_for_pdf(diet)
    )

    return bytes(pdf.output())


def extract_values(
    llm,
    blood_report: str
) -> str:

    prompt = f"""
You are a clinical lab report parser.

Extract every test result from the blood report below.

For each test, return exactly one line in this format:

Test Name: value | Status | Reference: range

Rules:
- Status must be one of: HIGH, LOW, NORMAL
- Compare the result against the reference range provided in the report to determine status
- If a reference range is missing, set status to UNKNOWN
- Do not skip any test, even if the value looks unremarkable
- Do not add any commentary, headers, or explanations
- Use the exact test name as written in the report

Blood Report:
{blood_report}
"""

    return llm.invoke(prompt).text


def get_summary_and_diet(
    llm,
    extracted_values: str
) -> tuple[str, str]:

    prompt = f"""
You are an Indian clinical nutritionist.

Given the extracted blood work values below, respond in exactly two sections with these exact headers:

SECTION 1 - HEALTH SUMMARY

4-5 lines, simple language, what's off and what it means.

SECTION 2 - INDIAN DIET PLAN

Foods to eat more:
8-10 specific Indian foods like dal, sabzi, roti, rice.
For each food, note which blood value it may help.

Foods to avoid:
5-7 specific items.
For each food, note which blood value it may worsen.

Food only, no supplements.
Prioritize affordable, common Indian ingredients.

Blood Work Values:
{extracted_values}
"""

    response = llm.invoke(prompt).text

    if "SECTION 2" in response:
        summary_part, diet_part = response.split(
            "SECTION 2",
            1
        )
    else:
        summary_part = response
        diet_part = ""

    summary = (
        summary_part
        .replace(
            "SECTION 1 - HEALTH SUMMARY",
            ""
        )
        .strip()
    )

    diet = diet_part.lstrip(" -").strip()

    if diet.upper().startswith(
        "INDIAN DIET PLAN"
    ):
        diet = diet[
            len("INDIAN DIET PLAN"):
        ].strip()

    return summary, diet


# -----------------------------
# SESSION STATE
# -----------------------------

if "health_summary" not in st.session_state:
    st.session_state.health_summary = ""

if "diet_plan" not in st.session_state:
    st.session_state.diet_plan = ""

if "blood_report_text" not in st.session_state:
    st.session_state.blood_report_text = ""


# -----------------------------
# PAGE UI
# -----------------------------

st.title("Blood Work Analyzer")

st.caption(
    "Educational demonstration only — not medical advice."
)


left_col, right_col = st.columns(2)


# -----------------------------
# LEFT COLUMN
# -----------------------------

with left_col:

    st.warning(
        "For privacy, remove your name, DOB, address, "
        "patient ID, medical record number, and other "
        "identifying information before uploading."
    )

    st.file_uploader(
        "Upload a report (PDF or TXT) — or paste it below",
        type=["pdf", "txt"],
        key="uploaded_file",
        on_change=handle_upload,
    )

    st.info(
        "Report contents are processed using an external AI service."
    )

    blood_report = st.text_area(
        "Paste your blood work report",
        height=440,
        key="blood_report_text",
    )

    analyze_clicked = st.button(
        "Analyze",
        use_container_width=True,
    )


# -----------------------------
# RIGHT COLUMN
# -----------------------------

with right_col:

    summary_placeholder = st.empty()
    diet_placeholder = st.empty()
    download_placeholder = st.empty()

    if analyze_clicked:

        if not blood_report.strip():

            st.warning(
                "Please paste or upload a blood work report "
                "before analyzing."
            )

        else:

            with st.spinner(
                "Analyzing blood work..."
            ):

                llm = get_llm()

                extracted_values = extract_values(
                    llm,
                    blood_report
                )

                summary, diet = (
                    get_summary_and_diet(
                        llm,
                        extracted_values
                    )
                )

                st.session_state.health_summary = summary
                st.session_state.diet_plan = diet

    with summary_placeholder.container():

        render_box(
            "Health Summary",
            st.session_state.health_summary
            or "Results will appear here after analysis."
        )

    with diet_placeholder.container():

        render_box(
            "Suggested Diet Plan",
            st.session_state.diet_plan
            or "Results will appear here after analysis."
        )

    if st.session_state.health_summary:

        pdf_bytes = build_analysis_pdf(
            st.session_state.health_summary,
            st.session_state.diet_plan
        )

        with download_placeholder.container():

            st.download_button(
                "Download Analysis as PDF",
                data=pdf_bytes,
                file_name="blood_work_analysis.pdf",
                mime="application/pdf",
                use_container_width=True,
            )