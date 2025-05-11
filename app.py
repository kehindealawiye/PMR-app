# === PMR Dashboard App ===

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import re
from fpdf import FPDF

st.set_page_config(page_title="PMR Dashboard", layout="wide")
st.title("📊 Performance Management Report Dashboard")

# === Section: File Upload and Setup ===
st.sidebar.header("🗂️ Report Settings")
source_option = st.sidebar.radio("Choose data source:", ["Upload Excel File", "Enter Google Sheets Link"])
uploaded_file = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
sheet_link = st.sidebar.text_input("Or paste Google Sheets link")

df = None
if source_option == "Upload Excel File" and uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name="PMR")
elif source_option == "Enter Google Sheets Link" and sheet_link:
    try:
        sheet_id = sheet_link.split("/d/")[1].split("/")[0]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=PMR"
        df = pd.read_csv(url)
    except Exception as e:
        st.error(f"Error loading sheet: {e}")
        st.stop()

if df is None:
    st.warning("Upload a file or paste a valid link to proceed.")
    st.stop()

# === Section: Detect Quarter and Year ===
columns = df.columns.tolist()
available_quarters = sorted(set(re.findall(r"(Q\\d) Output Performance", " ".join(columns))))
available_years = sorted(set(re.findall(r"Y(\\d{4}) Approved Budget", " ".join(columns))))
quarter = st.sidebar.selectbox("Select Quarter", available_quarters)
year = st.sidebar.selectbox("Select Year", available_years)
