import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import re
from fpdf import FPDF

st.set_page_config(page_title="PMR Dashboard", layout="wide")
st.title("📊 Performance Management Report Dashboard")

# === File and Link Upload ===
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

# === Detect Quarters and Years ===
columns = df.columns.tolist()
available_quarters = sorted(set(re.findall(r"(Q\d) Output Performance", " ".join(columns))))
available_years = sorted(set(re.findall(r"Y(\d{4}) Approved Budget", " ".join(columns))))

if not available_quarters or not available_years:
    st.error("Missing expected columns like 'Q4 Output Performance' or 'Y2024 Approved Budget'.")
    st.stop()

quarter = st.sidebar.selectbox("Select Quarter", available_quarters)
year = st.sidebar.selectbox("Select Year", available_years)

# === Clean Columns ===
output_col = f"{quarter} Output Performance"
budget_col = f"{quarter} Budget Performance"
approved_col = f"Y{year} Approved Budget"
released_col = f"Budget Released as at {quarter}"
planned_col = f"Planned {quarter} Perf"
mda_col = "MDA REVISED"

df[output_col] = pd.to_numeric(df.get(output_col), errors="coerce")
df[budget_col] = pd.to_numeric(df.get(budget_col), errors="coerce")
df[approved_col] = pd.to_numeric(df.get(approved_col), errors="coerce")
df[released_col] = pd.to_numeric(df.get(released_col), errors="coerce")
df[planned_col] = df.get(planned_col, pd.Series([None] * len(df))).astype(str).str.replace("%", "").astype(float)
df["Cummulative TPR score"] = pd.to_numeric(df.get("Cummulative TPR score"), errors="coerce")

def tpr_category(score):
    if score >= 80: return "On Track"
    elif score >= 60: return "At Risk"
    return "Off Track"

df["TPR Status"] = df["Cummulative TPR score"].apply(tpr_category)

# === MDA Filter ===
if mda_col in df.columns:
    selected_mda = st.selectbox("Filter by MDA", ["All"] + sorted(df[mda_col].dropna().unique().tolist()))
    filtered_df = df if selected_mda == "All" else df[df[mda_col] == selected_mda]
else:
    st.warning("'MDA REVISED' column not found. MDA filter disabled.")
    filtered_df = df

# === KPIs ===
avg_output = filtered_df[output_col].mean(skipna=True)
avg_budget = filtered_df[budget_col].mean(skipna=True)
total_budget = filtered_df[approved_col].sum(skipna=True)
avg_planned_output = filtered_df[planned_col].mean(skipna=True)

col1, col2, col3 = st.columns(3)
col1.metric(f"Average {quarter} Output Performance", f"{avg_output:.2%}")
col2.metric(f"Average {quarter} Budget Performance", f"{avg_budget:.2%}")
col3.metric(f"Total Y{year} Approved Budget", f"₦{total_budget:,.0f}")

st.markdown("---")

# === Sector Chart (if available) ===
if "Sector" in df.columns:
    st.subheader("Sector-Level Performance")
    sector_summary = filtered_df.groupby("Sector")[[output_col, budget_col]].mean().reset_index()
    fig_sector = px.bar(sector_summary, x="Sector", y=[output_col, budget_col], barmode="group")
    st.plotly_chart(fig_sector, use_container_width=True)
else:
    st.info("No 'Sector' column found, skipping sector-level chart.")

# === Overall Performance Chart ===
st.subheader("Overall Performance Comparison")
def get_color(v): return "green" if v >= 0.7 else "orange" if v >= 0.5 else "red"

bar_df = pd.DataFrame({
    "Metric": [f"Output Performance ({avg_planned_output:.0f}% Planned)", "Budget Performance"],
    "Value": [avg_output, avg_budget],
    "Color": [get_color(avg_output), get_color(avg_budget)]
})

fig_bar = go.Figure()
for _, r in bar_df.iterrows():
    fig_bar.add_trace(go.Bar(x=[r["Metric"]], y=[r["Value"]], marker_color=r["Color"], text=f"{r['Value']:.0%}", textposition="outside"))
fig_bar.update_layout(yaxis=dict(title="Performance", range=[0, 1]), showlegend=False)
st.plotly_chart(fig_bar, use_container_width=True)

# === Drilldown Table ===
if mda_col in df.columns:
    st.subheader("Drilldown Table")
    st.dataframe(filtered_df[[
        "Sector" if "Sector" in df.columns else df.columns[0],
        mda_col,
        "Programme / Project",
        output_col,
        "TPR Status",
        budget_col,
        approved_col
    ]])
else:
    st.info("Drilldown table skipped – 'MDA REVISED' not found.")

# === Heatmap by MDA ===
if mda_col in df.columns:
    st.subheader("MDA Performance Heatmap")
    heat_df = df.groupby(mda_col)[[output_col, budget_col]].mean().reset_index()
    fig_heat = px.imshow(heat_df.set_index(mda_col), color_continuous_scale="RdYlGn")
    st.plotly_chart(fig_heat, use_container_width=True)

# === PDF Export ===
st.subheader("Export PDF Summary")
if st.button("Generate Summary PDF"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(200, 10, "Performance Summary", ln=True, align="C")
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, f"Avg {quarter} Output: {avg_output:.2%}", ln=True)
        pdf.cell(200, 10, f"Avg {quarter} Budget: {avg_budget:.2%}", ln=True)
        pdf.cell(200, 10, f"Planned Output: {avg_planned_output:.0f}%", ln=True)
        pdf.cell(200, 10, f"Total Y{year} Budget: ₦{total_budget:,.0f}", ln=True)
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, "Performance Legends", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, """
Output & Budget Performance:
• 🟩 Green: >=70%
• 🟨 Amber: 50 - 69%
• 🟥 Red: 0 - 49%

Cummulative TPR Score:
• 🟩 On Track: >=80%
• 🟨 At Risk: 60 - 79%
• 🟥 Off Track: 0 - 59%
        """)
        pdf.output(tmpfile.name)
        with open(tmpfile.name, "rb") as f:
            st.download_button("Download PDF", f, file_name=f"PMR_Summary_{quarter}_{year}.pdf")

# === CSV Download ===
st.subheader("Download Data")
@st.cache_data
def to_csv(df): return df.to_csv(index=False).encode("utf-8")
st.download_button("Download as CSV", to_csv(filtered_df), f"pmr_data_{quarter}_{year}.csv", "text/csv")
