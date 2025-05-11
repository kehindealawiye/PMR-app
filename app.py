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
df["TPR Score"] = pd.to_numeric(df.get("TPR Score"), errors="coerce")

def tpr_category(score):
    if score >= 80: return "On Track"
    elif score >= 60: return "At Risk"
    return "Off Track"

df["TPR Status"] = df["TPR Score"].apply(tpr_category)

# === Section: TPR Filter ===
selected_tpr = st.sidebar.selectbox("Filter by TPR Status", ["All"] + sorted(df["TPR Status"].dropna().unique().tolist()))
filtered_df = df if selected_tpr == "All" else df[df["TPR Status"] == selected_tpr]

# === Section: Summary Cards ===
avg_output = filtered_df[output_col].mean(skipna=True)
avg_budget = filtered_df[budget_col].mean(skipna=True)
total_approved = filtered_df[approved_col].sum(skipna=True)
total_released = filtered_df[released_col].sum(skipna=True)
total_programmes = filtered_df["Programme / Project"].nunique()
total_kpis = filtered_df[kpi_col].count()
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
drill_cols = ["Programme / Project", output_col, planned_col, budget_col, released_col, "TPR Status"]
if "Sector" in df.columns: drill_cols.insert(0, "Sector")
if mda_col in df.columns: drill_cols.insert(1, mda_col)

def style_drilldown(df, output_col, budget_col):
    def highlight_perf(val):
        if pd.isna(val): return ""
        if val >= 0.7: return "background-color: #b6e8b0"
        elif val >= 0.5: return "background-color: #fff4b3"
        return "background-color: #f4b9b9"
    return df.style.applymap(highlight_perf, subset=[output_col, budget_col])

styled_table = style_drilldown(filtered_df[drill_cols], output_col, budget_col)
st.dataframe(styled_table, use_container_width=True)

# === Section: Pivot Table Explorer ===
st.subheader("Explore with Pivot Table")
all_columns = df.columns.tolist()
row = st.selectbox("Row", all_columns)
col = st.selectbox("Column", all_columns)
val = st.selectbox("Value", all_columns)
aggfunc = st.selectbox("Aggregation", ["sum", "mean", "count", "min", "max"])

if st.button("Generate Pivot Table"):
    try:
        pivot = pd.pivot_table(df, index=row, columns=col, values=val, aggfunc=aggfunc)
        st.dataframe(pivot)
    except Exception as e:
        st.error(f"Error generating pivot: {str(e)}")

# === Section: PDF Export ===
st.subheader("Export PDF Summary")
def encode_latin(text): return text.encode("latin-1", "ignore").decode("latin-1")

if st.button("Generate Summary PDF"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(200, 10, encode_latin("Performance Summary"), ln=True, align="C")
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, encode_latin(f"Avg {quarter} Output: {avg_output:.2%}"), ln=True)
        pdf.cell(200, 10, encode_latin(f"Avg {quarter} Budget: {avg_budget:.2%}"), ln=True)
        pdf.cell(200, 10, encode_latin(f"Planned Output: {avg_planned:.0f}%"), ln=True)
        pdf.cell(200, 10, encode_latin(f"Y{year} Approved Budget: ₦{total_approved:,.0f}"), ln=True)
        pdf.cell(200, 10, encode_latin(f"Budget Released at {quarter}: ₦{total_released:,.0f}"), ln=True)
        pdf.cell(200, 10, encode_latin(f"Projects: {total_programmes:,} | KPIs: {total_kpis:,}"), ln=True)
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, encode_latin("Performance Legends"), ln=True)
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

# === Section: CSV Export ===
st.subheader("Download Cleaned Data")

@st.cache_data
def convert_to_csv(df): return df.to_csv(index=False).encode("utf-8")
csv = convert_to_csv(filtered_df)
st.download_button("Download CSV", csv, f"pmr_cleaned_{quarter}_{year}.csv", "text/csv")
