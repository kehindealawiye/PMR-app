# === PMR Dashboard App ===

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import streamlit.components.v1 as components
from pivottablejs import pivot_ui
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
df.columns = [col.strip() for col in df.columns]
columns = df.columns.tolist()
available_quarters = sorted(set(re.findall(r"(Q\d) Output Performance", " ".join(columns))))
available_years = sorted(set(re.findall(r"Y(\d{4}) Approved Budget", " ".join(columns))))

if not available_quarters:
    st.warning("No column like 'Q4 Output Performance' found.")
    st.stop()
if not available_years:
    st.warning("No column like 'Y2024 Approved Budget' found.")
    st.stop()

quarter = st.sidebar.selectbox("Select Quarter", available_quarters)
year = st.sidebar.selectbox("Select Year", available_years)

# === Section: Column Mapping ===
output_col = f"{quarter} Output Performance"
budget_col = f"{quarter} Budget Performance"
approved_col = f"Y{year} Approved Budget"
released_col = f"Budget Released as at {quarter}"
planned_col = f"Planned {quarter} Perf"
mda_col = "MDA REVISED"
kpi_col = f"{quarter} Output Target (in numbers)"

# === Section: Clean Data ===
df[output_col] = pd.to_numeric(df.get(output_col), errors="coerce")
df[budget_col] = pd.to_numeric(df.get(budget_col), errors="coerce")
df[approved_col] = pd.to_numeric(df.get(approved_col), errors="coerce")
df[released_col] = pd.to_numeric(df.get(released_col), errors="coerce")
df[planned_col] = df.get(planned_col, pd.Series([None] * len(df))).astype(str).str.replace("%", "").astype(float)
df[kpi_col] = pd.to_numeric(df.get(kpi_col), errors="coerce")

# Fix TPR Score handling (decimal vs whole number)
if "Cummulative TPR Score" in df.columns:
    raw = pd.to_numeric(df["Cummulative TPR Score"], errors="coerce")
    df["TPR Score"] = raw if raw.max() <= 1 else raw / 100
else:
    st.error("Column 'Cummulative TPR Score' not found in uploaded data.")
    st.stop()

# Assign TPR Status
def tpr_category(score):
    if pd.isna(score): return None
    if score >= 0.8: return "On Track"
    elif score >= 0.6: return "At Risk"
    else: return "Off Track"

df["TPR Status"] = df["TPR Score"].apply(tpr_category)

# === Section: Dashboard Filters ===
st.subheader("Filters")

colf1, colf2 = st.columns(2)
tpr_options = ["All"] + sorted(df["TPR Status"].dropna().unique().tolist())
selected_tpr = colf1.selectbox("TPR Status", tpr_options)

mda_options = ["All"] + sorted(df[mda_col].dropna().unique().tolist())
selected_mda = colf2.selectbox("MDA", mda_options)

filtered_df = df.copy()
if selected_tpr != "All":
    filtered_df = filtered_df[filtered_df["TPR Status"] == selected_tpr]
if selected_mda != "All":
    filtered_df = filtered_df[filtered_df[mda_col] == selected_mda]

# === Section: Summary Cards ===
avg_output = filtered_df[output_col].mean(skipna=True)
avg_budget = filtered_df[budget_col].mean(skipna=True)
total_approved = filtered_df[approved_col].sum(skipna=True)
total_released = filtered_df[released_col].sum(skipna=True)
total_programmes = filtered_df["Programme / Project"].nunique()
total_kpis = filtered_df["Full Year Output Targets for Programme / Project Activities"].count()
avg_planned = filtered_df[planned_col].mean(skipna=True)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(f"Avg {quarter} Output", f"{avg_output:.2%}")
col2.metric(f"Avg {quarter} Budget", f"{avg_budget:.2%}")
col3.metric(f"Y{year} Budget", f"₦{total_approved:,.0f}")
col4.metric(f"Released at {quarter}", f"₦{total_released:,.0f}")
col5.metric("Projects", f"{total_programmes:,}")
col6, col7 = st.columns(2)
col6.metric("Total KPIs", f"{total_kpis:,}")

# === Section: Donut Charts ===
def donut_chart(value, label):
    zone = "green" if value >= 0.7 else "orange" if value >= 0.5 else "red"
    chart = go.Figure(go.Pie(
        labels=["Achieved", "Remaining"],
        values=[value, 1 - value],
        hole=0.6,
        marker=dict(colors=[zone, "#E0E0E0"]),
        textinfo='label+percent'
    ))
    chart.update_layout(title=label, showlegend=False)
    return chart

col8, col9 = st.columns(2)
col8.plotly_chart(donut_chart(avg_output, "Output Performance"), use_container_width=True)
col9.plotly_chart(donut_chart(avg_budget, "Budget Performance"), use_container_width=True)

# === Section: Drilldown Table ===
st.subheader("Drilldown Table")

# Exact matching columns
output_col = f"{quarter} Output Performance"
budget_col = f"{quarter} Budget Performance"
released_col = f"Budget Released as at {quarter}"
planned_col = f"Planned {quarter} Perf"
approved_col = f"Y{year} Approved Budget"
tpr_score_col = "Cummulative TPR Score"

drill_cols = [
    "Programme / Project",
    output_col,
    planned_col,
    budget_col,
    released_col,
    tpr_score_col,
    "TPR Status"
]
if "Sector" in df.columns:
    drill_cols.insert(0, "Sector")
if "MDA REVISED" in df.columns:
    drill_cols.insert(1, "MDA REVISED")

def style_drilldown(df, output_col, budget_col, approved_col, released_col, planned_col, tpr_score_col):
    def highlight_perf(val):
        if pd.isna(val): return ""
        if val >= 0.7: return "background-color: #b6e8b0"  # green
        elif val >= 0.5: return "background-color: #fff4b3"  # amber
        return "background-color: #f4b9b9"  # red

    def highlight_tpr(val):
        if pd.isna(val): return ""
        if val >= 0.8: return "background-color: #b6e8b0"
        elif val >= 0.6: return "background-color: #fff4b3"
        return "background-color: #f4b9b9"

    styled = df.style\
        .applymap(highlight_perf, subset=[output_col, budget_col])\
        .applymap(highlight_tpr, subset=[tpr_score_col])\
        .format({
            output_col: "{:.0%}",
            planned_col: "{:.0f}%",
            tpr_score_col: "{:.0%}",
            approved_col: "₦{:,.0f}",
            released_col: "₦{:,.0f}",
            budget_col: "{:.0%}",
        })

    return styled

# Ensure columns exist before applying
available_cols = [col for col in drill_cols if col in filtered_df.columns]
styled_table = style_drilldown(filtered_df[available_cols], output_col, budget_col, approved_col, released_col, planned_col, tpr_score_col)
st.dataframe(styled_table, use_container_width=True)


# === Section: Explore with Interactive Pivot Table ===
st.subheader("Explore with Interactive Pivot Table")
with st.spinner("Rendering pivot table..."):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        pivot_ui(filtered_df, outfile_path=tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            pivot_html = f.read()
            components.html(pivot_html, height=600, scrolling=True)

st.subheader("Export PDF Summary")

def encode_latin(text):
    return text.encode("latin-1", "ignore").decode("latin-1")

if st.button("Generate Summary PDF"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf = FPDF()
        pdf.add_page()

        # Header
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, encode_latin(f"{quarter} {year} Performance Dashboard Summary"), ln=True, align="C")
        pdf.ln(10)

        # Section: Summary Metrics
        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 10, encode_latin("Summary Metrics"), ln=True)
        pdf.set_font("Arial", "", 12)

        pdf.cell(90, 10, encode_latin("Average Output Performance:"), border=0)
        pdf.cell(0, 10, encode_latin(f"{avg_output:.2%}"), ln=True)

        pdf.cell(90, 10, encode_latin("Average Budget Performance:"), border=0)
        pdf.cell(0, 10, encode_latin(f"{avg_budget:.2%}"), ln=True)

        pdf.cell(90, 10, encode_latin("Planned Output Performance:"), border=0)
        pdf.cell(0, 10, encode_latin(f"{avg_planned:.0f}%"), ln=True)

        pdf.cell(90, 10, encode_latin(f"Y{year} Approved Budget:"), border=0)
        pdf.cell(0, 10, encode_latin(f"₦{total_approved:,.0f}"), ln=True)

        pdf.cell(90, 10, encode_latin(f"Budget Released at {quarter}:"), border=0)
        pdf.cell(0, 10, encode_latin(f"₦{total_released:,.0f}"), ln=True)

        pdf.cell(90, 10, encode_latin("Total Projects:"), border=0)
        pdf.cell(0, 10, encode_latin(f"{total_programmes:,}"), ln=True)

        pdf.cell(90, 10, encode_latin("Total KPIs:"), border=0)
        pdf.cell(0, 10, encode_latin(f"{total_kpis:,}"), ln=True)

        pdf.ln(10)

        # Section: Performance Legends
        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 10, encode_latin("Performance Legends"), ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, encode_latin("""
Output & Budget Performance:
• 🟩 Green: >=70%
• 🟨 Amber: 50 - 69%
• 🟥 Red: 0 - 49%

TPR Score:
• 🟩 On Track: >=80%
• 🟨 At Risk: 60 - 79%
• 🟥 Off Track: 0 - 59%
"""))

        pdf.output(tmpfile.name)
        with open(tmpfile.name, "rb") as f:
            st.download_button("Download PDF", f, file_name=f"PMR_Summary_{quarter}_{year}.pdf")
