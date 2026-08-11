# Task: Build Blood Work Analyzer Streamlit App

## File
Create: health_analysis/streamlit_app/app.py

## What it does
Streamlit app that takes a pasted blood work report, analyzes it with an LLM in two stages, and shows results.

## Layout
- Two equal columns
- Left column: text area (height 500) for pasting blood report + full-width "Analyze" button
- Right column: two dark-themed scrollable boxes (height 230px, background #1e1e1e, border #333, rounded corners) — one for "Health Summary", one for "Suggested Diet Plan"

## LLM Setup
- Use ChatGoogleGenerativeAI from langchain_google_genai
- Model: gemma-4-31b-it
- Load API key from .env using load_dotenv()

## Two-stage LLM Pipeline
Stage 1 — Extraction: Send the blood report to the LLM. Ask it to extract ALL test values and classify each as HIGH/LOW/NORMAL based on reference ranges. Format: "Test Name: value | Status | Reference: range"

Stage 2 — Diet advice: Send the extracted values to the LLM. Ask for two clearly labeled sections — "SECTION 1 - HEALTH SUMMARY" (4-5 lines, simple language) and "SECTION 2 - INDIAN DIET PLAN" (foods to eat more, foods to avoid, common Indian foods like dal, sabzi, roti, rice).

## Response Handling
- Split the Stage 2 response on "SECTION 2" to separate health summary from diet plan
- Strip section headers before displaying
- Render each part inside the scrollable boxes using unsafe_allow_html
- Show a warning if text area is empty when Analyze is clicked
- Show a spinner during analysis

## Config
- page_title: "Blood Work Analyzer"
- layout: wide