
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
import tempfile
import os
import re
import plotly.io as pio

# --- Sidebar Controls ---
st.set_page_config(page_title="PMR Generator", layout="wide")
st.sidebar.header("🗂️ Report Settings")
year = st.sidebar.text_input("Enter Report Year", "Y2025")
quarter = st.sidebar.selectbox("Select Quarter", ["Q1", "Q2", "Q3", "Q4"])
pdf_layout = st.sidebar.radio("PDF Layout", ["Portrait", "Landscape"])
custom_headers = st.sidebar.checkbox("Enable Manual Header Mapping")

st.title(f"📊 {quarter} {year} Performance Management Report Generator")

# --- Upload File ---
st.subheader("📨 Upload PMR Dataset")
uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "csv"])
sheet_url = st.text_input("Or paste public Google Sheets link")

df = None
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file, sheet_name=None).get("PMR", None)
        if df is None:
            st.error("❌ 'PMR' sheet not found.")
elif sheet_url:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    if match:
        sheet_id = match.group(1)
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=PMR"
        df = pd.read_csv(export_url)
    else:
        st.error("❌ Invalid Google Sheets URL.")

# --- Process ---
if df is not None:
    df['Q1 Output Target (in numbers)'] = pd.to_numeric(df['Q1 Output Target (in numbers)'], errors='coerce').fillna(0)
    df['Programme / Project'] = df['Programme / Project'].astype(str)
    df['Planned Q1 Perf'] = pd.to_numeric(df['Planned Q1 Perf'], errors='coerce').fillna(0)

    total_mdas = df['MDA REVISED'].nunique()
    total_programmes = df['Programme / Project'].nunique()
    total_kpis = df['Q1 Output Target (in numbers)'].count()
    cofog_counts = df.groupby("COFOG")['MDA REVISED'].nunique().to_dict()

    summary_text = (
        f"The Monitoring and Evaluation Department (MED) plays a central role in ensuring that government funding delivers "
        f"value through the execution of transformative policies, programmes, and strategies, in line with globally accepted best practices.\n\n"
        f"This {year} Performance Management Report (PMR) presents insights from {total_mdas} Ministries, Departments, and Agencies (MDAs) "
        f"implementing a total of {total_programmes} Programmes/Projects, tracked using {total_kpis} Key Performance Indicators (KPIs). "
        f"All MDAs are classified under the internationally recognized Classification of the Functions of Government (COFOG) framework.\n\n"
        f"#### Sector Distribution (COFOG Classification):\n"
    )
    for sector, count in cofog_counts.items():
        summary_text += f"- {sector} – {count} MDAs\n"

    summary_text += (
        "\n#### Performance Dimensions:\n"
        "- Programme/Project Performance: Evaluates the achievement of set output targets.\n"
        "- Budget Performance: Assesses the extent to which allocated budgets were effectively utilized.\n\n"
        "#### Cross-Cutting Insights and Recommendations:\n"
        "- Efficiency in Expenditure\n"
        "- Data-Driven Decision Making\n"
        "- Monitoring and Evaluation\n"
        "- Stakeholder Engagement\n"
        "- Capacity Building"
    )

    objectives_text = (
        "- Tracking Progress\n"
        "- Answering Key Questions\n"
        "- Guiding Budget and Plans\n"
        "- Understanding Impact"
    )

    overview_text = (
        "Performance Management in Lagos State involves a strategic and cohesive approach to public sector performance, "
        "ensuring the achievement of planned outcomes, accountability, and value for money in governance."
    )

    # Generate Sector Chart
    mda_df = df.groupby(['COFOG', 'MDA REVISED']).agg(
        TOTAL_PROGRAMMES=('Programme / Project', 'nunique'),
        TOTAL_KPIs=('Q1 Output Target (in numbers)', 'count'),
        AVG_OUTPUT_PERF=('Q1 PMR Output Performance', 'mean'),
        TOTAL_BUDGET=('Y2025 Approved Budget', 'sum'),
        BUDGET_RELEASED=('Budget Released as at Q1', 'sum')
    ).reset_index()
    mda_df['AVG_BUDGET_PERF'] = (mda_df['BUDGET_RELEASED'] / mda_df['TOTAL_BUDGET'].replace(0, pd.NA)).fillna(0) * 100
    sector = df['COFOG'].unique()[0]
    selected_sector_df = mda_df[mda_df['COFOG'] == sector]
    fig_sector = px.bar(selected_sector_df, x="MDA REVISED", y=["AVG_OUTPUT_PERF", "AVG_BUDGET_PERF"], barmode="group")

    # Generate Annexure Chart
    mda = df[df['COFOG'] == sector]['MDA REVISED'].unique()[0]
    ann_df = df[(df['COFOG'] == sector) & (df['MDA REVISED'] == mda)]
    avg_output = ann_df['Q1 PMR Output Performance'].mean()
    avg_planned = ann_df['Planned Q1 Perf'].mean()
    avg_budget = (ann_df['Budget Released as at Q1'].sum() / ann_df['Y2025 Approved Budget'].sum()) * 100

    def perf_color(val): return 'red' if val < 50 else 'orange' if val < 70 else 'green'

    fig_ann = go.Figure()
    fig_ann.add_trace(go.Bar(x=[avg_output], y=["Output Performance"], orientation='h',
        text=[f"{avg_output:.1f}% (Planned: {avg_planned:.1f}%)"], marker_color=perf_color(avg_output)))
    fig_ann.add_trace(go.Bar(x=[avg_budget], y=["Budget Performance"], orientation='h',
        text=[f"{avg_budget:.1f}%"], marker_color=perf_color(avg_budget)))
    fig_ann.update_layout(title=f"{mda} Performance", xaxis=dict(range=[0, 100]), height=300)

    # --- Export PDF ---
    # The rest of the code generates the preview and ends with:
    # if st.button("📥 Download Final PDF"):

    if st.button("📥 Download Final PDF"):
        
        with st.spinner("📦 Exporting PDF..."):
            pio.kaleido.scope.default_format = "png"

            class PDF(FPDF):
                def header(self):
                    self.set_font("Arial", "I", 8)
                    self.cell(0, 10, f"{quarter} {year} PMR | MEPB", 0, 1, 'C')

                def footer(self):
                    self.set_y(-15)
                    self.set_font("Arial", "I", 8)
                    self.cell(0, 10, f"Page {self.page_no()}", 0, 0, 'C')

            def add_chart(fig, pdf, title="Chart"):
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, title, ln=True)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                    fig.write_image(tmp_img.name)
                    pdf.image(tmp_img.name, x=15, w=180)

            def add_text_page(pdf, title, content):
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, title, ln=True)
                pdf.set_font("Arial", "", 12)
                for line in content.strip().split("\n"):
                    pdf.multi_cell(0, 10, line.strip())

            def add_table(pdf, title, df_table):
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, title, ln=True)
                pdf.set_font("Arial", "", 10)
                for _, row in df_table.iterrows():
                    line = " | ".join(str(row[col]) for col in df_table.columns)
                    pdf.multi_cell(0, 6, line)

            layout_mode = 'P' if pdf_layout == 'Portrait' else 'L'
            pdf = PDF(orientation=layout_mode, unit='mm', format='A4')
            pdf.set_auto_page_break(auto=True, margin=15)

            # --- Cover Page ---
            pdf.add_page()
            if os.path.exists("cover_page.png"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                    img = Image.open("cover_page.png").convert("RGB")
                    draw = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("arial.ttf", 32)
                    except:
                        font = ImageFont.load_default()
                    draw.text((50, img.height - 80), f"{quarter} {year}", fill="black", font=font)
                    img.save(temp_img.name)
                    pdf.image(temp_img.name, x=0, y=0, w=210 if layout_mode == 'P' else 297)

            # --- TOC ---
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "Table of Contents", ln=True)
            toc = [
                "1.1 PMR Overview", "1.2 PMR Objectives", "1.3 Executive Summary",
                "1.4 Tabular Summary by COFOG", "1.5 Graphical Summary by COFOG",
                "2.0 MDA Chart by Sector", "3.0 Annexure (by MDA)"
            ]
            pdf.set_font("Arial", "", 12)
            for i, t in enumerate(toc, 1):
                pdf.cell(0, 8, f"{t} ............................................... {i + 2}", ln=True)

            # Text Content
            overview_text = "Performance Management in Lagos State involves a strategic and cohesive approach to public sector performance."
            objectives_text = "- Tracking Progress\n- Answering Key Questions\n- Guiding Budget and Plans\n- Understanding Impact"
            summary_text = f"This report covers {total_mdas} MDAs, {total_programmes} projects, and {total_kpis} KPIs.\n\n"
            for sector, count in cofog_counts.items():
                summary_text += f"{sector}: {count} MDAs\n"
            summary_text += "\nRecommendations:\n- Efficiency in Expenditure\n- Data-Driven Decisions\n- M&E\n- Stakeholder Engagement\n- Capacity Building"

            add_text_page(pdf, "1.1 PMR Overview", overview_text)
            add_text_page(pdf, "1.2 PMR Objectives", objectives_text)
            add_text_page(pdf, "1.3 Executive Summary", summary_text)
            add_table(pdf, "1.4 Tabular Summary by COFOG", cofog_summary)
            add_chart(fig_cofog, pdf, "1.5 Graphical Summary by COFOG")

            for sector in mda_df['COFOG'].unique():
                filtered = mda_df[mda_df['COFOG'] == sector]
                fig = px.bar(filtered, x="MDA REVISED", y=["AVG_OUTPUT_PERF", "AVG_BUDGET_PERF"], barmode="group")
                add_chart(fig, pdf, f"2.0 MDA Chart by Sector – {sector}")

            def perf_color(val): return 'red' if val < 50 else 'orange' if val < 70 else 'green'
            for sector in df['COFOG'].unique():
                for mda in df[df['COFOG'] == sector]['MDA REVISED'].unique():
                    ann_df = df[(df['COFOG'] == sector) & (df['MDA REVISED'] == mda)]
                    avg_output = ann_df['Q1 PMR Output Performance'].mean()
                    avg_planned = ann_df['Planned Q1 Perf'].mean()
                    avg_budget = (ann_df['Budget Released as at Q1'].sum() / ann_df['Y2025 Approved Budget'].sum()) * 100
                    fig_ann = go.Figure()
                    fig_ann.add_trace(go.Bar(x=[avg_output], y=["Output Performance"], orientation='h',
                        text=[f"{avg_output:.1f}% (Planned: {avg_planned:.1f}%)"], marker_color=perf_color(avg_output)))
                    fig_ann.add_trace(go.Bar(x=[avg_budget], y=["Budget Performance"], orientation='h',
                        text=[f"{avg_budget:.1f}%"], marker_color=perf_color(avg_budget)))
                    fig_ann.update_layout(title=f"{mda} Performance", xaxis=dict(range=[0, 100]), height=250)
                    add_chart(fig_ann, pdf, f"3.0 Annexure – {mda}")
                    table_cols = ['State Level Goal', 'Outcome', 'Programme / Project', 'Q1 Actual Output', 'Remarks']
                    add_table(pdf, f"{mda} Annexure Data", ann_df[table_cols])

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
                pdf.output(tmpfile.name)
                with open(tmpfile.name, "rb") as f:
                    st.download_button("⬇️ Download Final PDF", data=f.read(), file_name=f"PMR_Report_{quarter}_{year}.pdf", mime="application/pdf")
