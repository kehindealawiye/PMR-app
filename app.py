# === PMR Dashboard App === 

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tempfile
from datetime import datetime
import re
import os
import zipfile
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        try:
            self.image("Lagos-logo.png", x=10, y=8, w=25)
        except:
            pass

def encode_latin(text):
    return text.encode("latin-1", "ignore").decode("latin-1")
    

st.set_page_config(page_title="PMR Dashboard", layout="wide")
st.title("📊 Performance Management Report Dashboard")

# === Section: File Upload and Setup ===
st.sidebar.header("🗂️ Report Settings")

source_option = st.sidebar.radio(
    "Choose data source:",
    ["Use GitHub default", "Upload Excel File", "Enter Google Sheets Link"]
)

df = None

if source_option == "Use GitHub default":
    try:
        github_url = "https://raw.githubusercontent.com/kehindealawiye/PMR-app/refs/heads/main/Y2024%20PMR%20dummy.xlsx"
        df = pd.read_excel(github_url, sheet_name="PMR", engine="openpyxl")
        st.sidebar.success("Loaded default file from GitHub.")
    except Exception as e:
        st.sidebar.error(f"Failed to load default sheet: {e}")
        st.stop()

elif source_option == "Upload Excel File":
    uploaded_file = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file, sheet_name="PMR")
    else:
        st.warning("Please upload a file to continue.")
        st.stop()

elif source_option == "Enter Google Sheets Link":
    sheet_link = st.sidebar.text_input("Paste your Google Sheets link")
    if sheet_link:
        try:
            sheet_id = sheet_link.split("/d/")[1].split("/")[0]
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=PMR"
            df = pd.read_csv(url)
        except Exception as e:
            st.error(f"Error loading sheet: {e}")
            st.stop()
    else:
        st.warning("Please paste a link to continue.")
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
sector_col = "COFOG"
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

colf1, colf2, colf3, colf4 = st.columns(4)

# TPR Status
tpr_options = ["All"] + sorted(df["TPR Status"].dropna().unique().tolist())
selected_tpr = colf1.selectbox("TPR Status", tpr_options)

# Sector
sector_options = ["All"] + sorted(df["COFOG"].dropna().unique().tolist())
selected_sector = colf2.selectbox("Sector", sector_options)

# MDA (filtered by Sector)
if selected_sector != "All":
    mda_subset = df[df["COFOG"] == selected_sector]
else:
    mda_subset = df

mda_options = ["All"] + sorted(mda_subset[mda_col].dropna().unique().tolist())
selected_mda = colf3.selectbox("MDA", mda_options)

# Programme/Project (filtered by MDA)
if selected_mda != "All":
    proj_subset = mda_subset[mda_subset[mda_col] == selected_mda]
else:
    proj_subset = mda_subset

proj_options = ["All"] + sorted(proj_subset["Programme / Project"].dropna().unique().tolist())
selected_proj = colf4.selectbox("Programme / Project", proj_options)

# Apply filters
filtered_df = df.copy()
if selected_tpr != "All":
    filtered_df = filtered_df[filtered_df["TPR Status"] == selected_tpr]
if selected_sector != "All":
    filtered_df = filtered_df[filtered_df["Sector"] == selected_sector]
if selected_mda != "All":
    filtered_df = filtered_df[filtered_df[mda_col] == selected_mda]
if selected_proj != "All":
    filtered_df = filtered_df[filtered_df["Programme / Project"] == selected_proj]
    
    
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
# === Drilldown Table Columns ===
output_col = f"{quarter} Output Performance"
budget_col = f"{quarter} Budget Performance"
released_col = f"Budget Released as at {quarter}"
planned_col = f"Planned {quarter} Perf"
approved_col = f"Y{year} Approved Budget"
tpr_score_col = "Cummulative TPR Score"
targets_col = "Full Year Output Targets for Programme / Project Activities"
actual_col = f"{quarter} Actual Output"
sector_col = "COFOG"

drill_cols = [
    sector_col,
    "Programme / Project",
    targets_col,
    actual_col,
    output_col,
    planned_col,
    tpr_score_col,
    "TPR Status",
    approved_col,
    released_col,
    budget_col,
    "Remarks"
]

# Insert Sector and MDA Revised at the top if present
if "COFOG" in df.columns:
    drill_cols.insert(0, "COFOG")
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
st.caption(f"{len(filtered_df)} records matched your filters.")
st.dataframe(styled_table, use_container_width=True)

# === Section: Pivot Table Explorer ===
st.subheader("Explore with Pivot Table")

col1, col2 = st.columns(2)
rows = col1.multiselect("Row(s)", df.columns.tolist())
cols = col2.multiselect("Column(s)", df.columns.tolist())
val = st.multiselect("Value(s)", df.columns.tolist())
aggfunc = st.selectbox("Aggregation", ["sum", "mean", "count", "min", "max"])

if st.button("Generate Pivot Table"):
    if filtered_df.empty:
        st.warning("No data available based on current filters.")
        st.stop()

    if not val:
        st.warning("Please select at least one value column.")
        st.stop()

    # Ensure value columns have usable data
    if all(filtered_df[v].dropna().empty for v in val):
        st.warning("No usable data found in selected value columns after filtering.")
        st.stop()

    try:
        for v in val:
            filtered_df[v] = pd.to_numeric(filtered_df[v], errors="coerce")

        # Debug preview
        preview_cols = list(set((rows or []) + (cols or []) + val))
        st.caption("Preview of data before pivot:")
        st.dataframe(filtered_df[preview_cols].dropna().head())

        pivot = pd.pivot_table(
            filtered_df,
            index=rows if rows else None,
            columns=cols if cols else None,
            values=val,
            aggfunc=aggfunc,
            margins=False,
            dropna=False  # Show all combinations even if result is NaN
        )

        if pivot.shape[0] == 0 or pivot.shape[1] == 0:
            st.warning("Pivot table returned no rows or columns.")
            st.stop()

        # Format output
        if len(val) == 1:
            col = val[0]
            if "Performance" in col or "TPR" in col:
                styled = pivot.style.format({col: "{:.0%}"})
            elif "Budget" in col or "Approved" in col or "Released" in col:
                styled = pivot.style.format({col: "₦{:,.0f}"})
            else:
                styled = pivot
            st.dataframe(styled, use_container_width=True)
        else:
            st.dataframe(pivot, use_container_width=True)

    except Exception as e:
        st.error(f"Error generating pivot table: {str(e)}")
        

# === Section: Export PDF Summary (Sector/MDA below, Footer adjusted) ===
st.subheader("Export PDF Summary")

from datetime import datetime
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        try:
            self.image("Lagos-logo.png", x=10, y=8, w=25)
        except:
            pass

def encode_latin(text):
    return text.encode("latin-1", "ignore").decode("latin-1")

if st.button("Download PDF Summary"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf = PDF(orientation="L")
        pdf.add_page()

        # Title (centered)
        pdf.set_xy(40, 10)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 8, encode_latin(f"{quarter} {year} Performance Dashboard Summary"), align="C")
        pdf.ln(10)

        # KPI card setup
        kpi_blocks = [
            ("output.png", "Average output performance", f"{avg_output:.2%}", (210, 230, 255)),
            ("budget.png", "Average budget performance", f"{avg_budget:.2%}", (220, 255, 220)),
            ("approved.png", "Total budget approved", f"₦{total_approved:,.0f}", (255, 255, 210)),
            ("released.png", "Total budget released", f"₦{total_released:,.0f}", (255, 230, 200)),
            ("projects.png", "Total number of programmes/projects", f"{total_programmes:,}", (235, 230, 255)),
            ("kpi.png", "Total number of KPIs", f"{total_kpis:,}", (240, 240, 240))
        ]

        block_width = 90
        spacing = 10
        icon_size = 12
        block_height = 9
        margin_left = (pdf.w - (3 * block_width + 2 * spacing)) / 2

        def draw_kpi_card(x, y, icon, label, value, bg_color):
            try:
                pdf.image(icon, x + block_width / 2 - icon_size / 2, y, w=icon_size)
            except:
                pass
            y += icon_size + 1
            pdf.set_xy(x, y)
            pdf.set_fill_color(*bg_color)
            pdf.set_draw_color(200, 200, 200)
            pdf.set_font("Arial", "B", 9)
            pdf.multi_cell(block_width, block_height, encode_latin(label), border=1, align="C", fill=True)
            y += block_height
            pdf.set_xy(x, y)
            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(block_width, block_height + 1, encode_latin(value), border=1, align="C", fill=True)

        y_top = pdf.get_y() + 25
        for i in range(3):
            x = margin_left + i * (block_width + spacing)
            draw_kpi_card(x, y_top, *kpi_blocks[i])

        y_bottom = y_top + (icon_size + block_height * 2 + 8)
        for i in range(3, 6):
            x = margin_left + (i - 3) * (block_width + spacing)
            draw_kpi_card(x, y_bottom, *kpi_blocks[i])

        # Sector and MDA (positioned just below the logo, above KPIs)
        pdf.set_xy(12, 35)  # Adjust Y to be slightly below the logo
        pdf.set_font("Arial", "B", 10)
        if selected_sector != "All":
            pdf.cell(0, 6, encode_latin(f"Sector: {selected_sector}"), ln=True)
        if selected_mda != "All":
            pdf.set_x(12)
            pdf.cell(0, 6, encode_latin(f"MDA: {selected_mda}"), ln=True)

        pdf.ln(25)  # Add some space before KPI cards

        pdf.output(tmpfile.name)
        with open(tmpfile.name, "rb") as f:
            st.download_button("Download PDF", f, file_name=f"PMR_Summary_{quarter}_{year}.pdf")
            

# === Section: Batch Export — One PDF with pages for each MDA in selected Sector ===
selected_sector_for_mda = st.selectbox("Select Sector for full MDA PDF", df["COFOG"].dropna().unique())

if st.button("Download All MDAs in Selected Sector as PDF"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf = PDF(orientation="L")

        # Define layout values
        block_width = 90
        spacing = 10
        icon_size = 12
        block_height = 9
        margin_left = (pdf.w - (3 * block_width + 2 * spacing)) / 2

        def draw_kpi_card(x, y, icon, label, value, bg_color):
            try:
                pdf.image(icon, x + block_width / 2 - icon_size / 2, y, w=icon_size)
            except:
                pass
            y += icon_size + 1
            pdf.set_xy(x, y)
            pdf.set_fill_color(*bg_color)
            pdf.set_draw_color(200, 200, 200)
            pdf.set_font("Arial", "B", 9)
            pdf.multi_cell(block_width, block_height, encode_latin(label), border=1, align="C", fill=True)
            y += block_height
            pdf.set_xy(x, y)
            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(block_width, block_height + 1, encode_latin(value), border=1, align="C", fill=True)

        mda_list = df[df["Sector"] == selected_sector_for_mda]["MDA REVISED"].dropna().unique()
        for mda_name in mda_list:
            mda_df = df[(df["Sector"] == selected_sector_for_mda) & (df["MDA REVISED"] == mda_name)]
            if mda_df.empty:
                continue

            avg_output = mda_df[output_col].mean(skipna=True)
            avg_budget = mda_df[budget_col].mean(skipna=True)
            total_approved = mda_df[approved_col].sum(skipna=True)
            total_released = mda_df[released_col].sum(skipna=True)
            total_programmes = mda_df["Programme / Project"].nunique()
            total_kpis = mda_df[targets_col].count()

            pdf.add_page()

            # Title
            pdf.set_xy(40, 10)
            pdf.set_font("Arial", "B", 14)
            pdf.multi_cell(0, 8, encode_latin(f"{quarter} {year} MDA Dashboard Summary"), align="C")

            # Sector and MDA info
            pdf.set_xy(12, 35)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, encode_latin(f"Sector: {selected_sector_for_mda}"), ln=True)
            pdf.set_x(12)
            pdf.cell(0, 6, encode_latin(f"MDA: {mda_name}"), ln=True)
            pdf.ln(5)  # space before cards

            # KPI blocks
            kpi_blocks = [
                ("output.png", "Average output performance", f"{avg_output:.2%}", (210, 230, 255)),
                ("budget.png", "Average budget performance", f"{avg_budget:.2%}", (220, 255, 220)),
                ("approved.png", "Total budget approved", f"₦{total_approved:,.0f}", (255, 255, 210)),
                ("released.png", "Total budget released", f"₦{total_released:,.0f}", (255, 230, 200)),
                ("projects.png", "Total number of programmes/projects", f"{total_programmes:,}", (235, 230, 255)),
                ("kpi.png", "Total number of KPIs", f"{total_kpis:,}", (240, 240, 240))
            ]

            y_top = pdf.get_y() + 10  # consistent offset
            for i in range(3):
                x = margin_left + i * (block_width + spacing)
                draw_kpi_card(x, y_top, *kpi_blocks[i])
            y_bottom = y_top + (icon_size + block_height * 2 + 8)
            for i in range(3, 6):
                x = margin_left + (i - 3) * (block_width + spacing)
                draw_kpi_card(x, y_bottom, *kpi_blocks[i])

            # Footer
            pdf.set_y(178)
            pdf.set_font("Arial", "I", 8)
            pdf.cell(0, 10, encode_latin(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), ln=True, align="R")

        pdf.output(tmpfile.name)
        with open(tmpfile.name, "rb") as f:
            st.download_button("Download Sector PDF", f, file_name=f"{selected_sector_for_mda}_MDAs_Summary.pdf")
            
