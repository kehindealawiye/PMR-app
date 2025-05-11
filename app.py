import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from urllib.parse import urlparse
from fpdf import FPDF
import tempfile
import re

st.set_page_config(page_title="PMR Dashboard", layout="wide")
st.title("📊 Performance Management Report Dashboard")

# === File Upload or Google Sheets ===
st.sidebar.header("🗂️ Report Settings")
source_option = st.sidebar.radio("Choose data source:", ["Upload Excel File", "Enter Google Sheets Link"])
uploaded_file = st.sidebar.file_uploader("Upload your PMR Excel file", type=["xlsx"])
sheet_link = st.sidebar.text_input("Paste Google Sheets link (public access required)")

# === Load Data ===
df = None
if source_option == "Upload Excel File" and uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name="PMR")
elif source_option == "Enter Google Sheets Link" and sheet_link:
    try:
        sheet_id = sheet_link.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=PMR"
        df = pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Error loading Google Sheet: {str(e)}")
        st.stop()

if df is None:
    st.info("Please upload an Excel file or enter a Google Sheets link to continue.")
    st.stop()

# === Detect Quarters and Years ===
columns = df.columns.tolist()
available_quarters = sorted(set(re.findall(r"(Q\d) Output Performance", " ".join(columns))))
available_years = sorted(set(re.findall(r"Y(\d{4}) Approved Budget", " ".join(columns))))
if not available_quarters or not available_years:
    st.error("Could not detect valid 'Qx Output Performance' or 'Yxxxx Approved Budget' columns.")
    st.stop()

quarter = st.sidebar.selectbox("Select Quarter", available_quarters)
year = st.sidebar.selectbox("Select Year", available_years)

# === Clean Data ===
df[f"{quarter} Output Performance"] = pd.to_numeric(df.get(f"{quarter} Output Performance"), errors="coerce")
df[f"{quarter} Budget Performance"] = pd.to_numeric(df.get(f"{quarter} Budget Performance"), errors="coerce")
df[f"Y{year} Approved Budget"] = pd.to_numeric(df.get(f"Y{year} Approved Budget"), errors="coerce")
df[f"Budget Released as at {quarter}"] = pd.to_numeric(df.get(f"Budget Released as at {quarter}"), errors="coerce")

planned_col = f"Planned {quarter} Perf"
if planned_col in df.columns:
    df[planned_col] = df[planned_col].str.replace("%", "", regex=False).astype(float)
else:
    df[planned_col] = float("nan")

df["Cummulative TPR score"] = pd.to_numeric(df.get("Cummulative TPR score"), errors="coerce")

def tpr_category(score):
    if score >= 80:
        return "On Track"
    elif score >= 60:
        return "At Risk"
    return "Off Track"

df["TPR Status"] = df["Cummulative TPR score"].apply(tpr_category)

# === KPI Summary ===
avg_output = df[f"{quarter} Output Performance"].mean(skipna=True)
avg_budget = df[f"{quarter} Budget Performance"].mean(skipna=True)
total_budget = df[f"Y{year} Approved Budget"].sum(skipna=True)

col1, col2, col3 = st.columns(3)
col1.metric(f"Average {quarter} Output Performance", f"{avg_output:.2%}")
col2.metric(f"Average {quarter} Budget Performance", f"{avg_budget:.2%}")
col3.metric(f"Total Y{year} Approved Budget", f"₦{total_budget:,.0f}")

st.markdown("---")

# === Sector Performance ===
st.subheader("Sector-Level Performance")
sector_summary = df.groupby("Sector")[[f"{quarter} Output Performance", f"{quarter} Budget Performance"]].mean().reset_index()
fig_sector = px.bar(sector_summary, x="Sector", y=[f"{quarter} Output Performance", f"{quarter} Budget Performance"], barmode="group")
st.plotly_chart(fig_sector, use_container_width=True)

# === Overall Bar Chart ===
st.subheader(f"Overall {quarter} Output and Budget Performance")
avg_planned_output = df[planned_col].mean(skipna=True)

def get_color(value):
    if value >= 0.7: return "green"
    if value >= 0.5: return "orange"
    return "red"

bar_data = pd.DataFrame({
    "Metric": [f"Output Performance ({avg_planned_output:.0f}% Planned)", "Budget Performance"],
    "Value": [avg_output, avg_budget],
    "Color": [get_color(avg_output), get_color(avg_budget)]
})

fig_bar = go.Figure()
for _, row in bar_data.iterrows():
    fig_bar.add_trace(go.Bar(
        x=[row["Metric"]],
        y=[row["Value"]],
        marker_color=row["Color"],
        text=f"{row['Value']:.0%}",
        textposition="outside"
    ))
fig_bar.update_layout(yaxis=dict(title="Performance", range=[0, 1]), showlegend=False)
st.plotly_chart(fig_bar, use_container_width=True)

# === MDA Explorer ===
st.subheader("Explore MDA Performance")
selected_sector = st.selectbox("Filter by Sector", ["All"] + sorted(df["Sector"].dropna().unique().tolist()))
selected_tpr = st.selectbox("Filter by TPR Status", ["All"] + sorted(df["TPR Status"].dropna().unique().tolist()))

filtered_df = df.copy()
if selected_sector != "All":
    filtered_df = filtered_df[filtered_df["Sector"] == selected_sector]
if selected_tpr != "All":
    filtered_df = filtered_df[filtered_df["TPR Status"] == selected_tpr]

st.dataframe(filtered_df[[
    "Sector", "MDA REVISED", "Programme / Project",
    f"{quarter} Output Performance", "TPR Status",
    f"{quarter} Budget Performance", f"Y{year} Approved Budget"
]])

# === Heatmap ===
st.subheader("MDA Performance Heatmap")
mda_perf = df.groupby("MDA REVISED")[[f"{quarter} Output Performance", f"{quarter} Budget Performance"]].mean().reset_index()
fig_heatmap = px.imshow(mda_perf.set_index("MDA REVISED"), color_continuous_scale="RdYlGn", labels={"color": "Performance"})
st.plotly_chart(fig_heatmap, use_container_width=True)

# === PDF Export ===
st.subheader("Export PDF Summary")
if st.button("Generate Summary PDF"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(200, 10, "Performance Summary", ln=True, align="C")

        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, f"Average {quarter} Output Performance: {avg_output:.2%}", ln=True)
        pdf.cell(200, 10, f"Average {quarter} Budget Performance: {avg_budget:.2%}", ln=True)
        pdf.cell(200, 10, f"Planned {quarter} Output Performance: {avg_planned_output:.0f}%", ln=True)
        pdf.cell(200, 10, f"Total Y{year} Approved Budget: ₦{total_budget:,.0f}", ln=True)

        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, "Performance Legends", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, """
Output & Budget Performance:
• 🟩 Green: >=70%
• 🟨 Amber: 50 - 69%
• 🟥 Red: 0 - 49%
(Note: 0% = Yet to commence, 100% = Completed)

Cummulative TPR Score:
• 🟩 Green (On Track): >=80%
• 🟨 Amber (At Risk): 60 - 79%
• 🟥 Red (Off Track): 0 - 59%
        """)
        pdf.output(tmpfile.name)
        with open(tmpfile.name, "rb") as f:
            st.download_button("Download PDF Report", f, file_name=f"PMR_Summary_{quarter}_{year}.pdf")

# === CSV Export ===
st.subheader("Download Cleaned Data")
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

csv = convert_df_to_csv(df)
st.download_button("Download Cleaned PMR Data as CSV", csv, f"cleaned_pmr_data_{quarter}_{year}.csv", "text/csv")
