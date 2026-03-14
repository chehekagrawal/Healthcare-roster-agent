import os
import time
from datetime import datetime
from fpdf import FPDF
from src.db.duckdb_engine import MetricsEngine
from src.tools.data_query import DataQueryTool

class ReportGenerator:
    """
    Operational Report Generator.
    Produces high-fidelity corporate PDF reports and structured Markdown summaries.
    """
    def __init__(self, metrics_engine: MetricsEngine):
        self.engine = metrics_engine
        self.query_tool = DataQueryTool(metrics_engine)

    def generate_pdf_report(self):
        """
        Produces a premium, high-fidelity PDF report with corporate styling,
        metric cards, and zebra-striped tables.
        """
        # 1. Fetch Data
        stuck_df = self.query_tool.derive_metrics("stuck_duration")
        health_df = self.query_tool.derive_metrics("health")
        market_df = self.engine.market_pipeline_correlation()
        avg_health = health_df['composite_health_score'].mean()
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- A. CORPORATE BANNER ---
        pdf.set_fill_color(14, 17, 23) # Deep Dark Blue (Match UI Theme)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B", 24)
        pdf.text(15, 20, "RosterIQ Intelligence")
        pdf.set_font("Arial", "", 12)
        pdf.text(15, 30, "Autonomous Pipeline Health & Market Diagnostics")
        
        pdf.set_y(45)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "I", 9)
        pdf.cell(0, 10, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='R')
        pdf.ln(5)

        # --- B. EXECUTIVE KPI CARDS ---
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Executive Summary", ln=True)
        pdf.ln(2)
        
        current_y = pdf.get_y()
        
        # Health Score Card (Greenish)
        pdf.set_fill_color(230, 255, 230)
        pdf.rect(15, current_y, 85, 25, 'F')
        pdf.set_xy(20, current_y + 5)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 10)
        pdf.cell(75, 5, "Overall Health Score", ln=True)
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(34, 139, 34)
        pdf.set_x(20)
        pdf.cell(75, 10, f"{avg_health:.2f} / 1.0", ln=True)
        
        # Stuck Count Card (Redish)
        pdf.set_fill_color(255, 235, 235)
        pdf.rect(105, current_y, 85, 25, 'F')
        pdf.set_xy(110, current_y + 5)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 10)
        pdf.cell(75, 5, "Total Stuck ROs", ln=True)
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(178, 34, 34)
        pdf.set_x(110)
        pdf.cell(75, 10, str(len(stuck_df)), ln=True)
        
        pdf.set_y(current_y + 35)
        pdf.set_text_color(0, 0, 0)

        # --- C. ACTIVE BOTTLENECKS TABLE ---
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Active Pipeline Bottlenecks", ln=True)
        
        headers = ["RO_ID", "Organization", "Stage", "Mins Stuck"]
        rows = []
        for _, row in stuck_df.sort_values('minutes_stuck', ascending=False).head(5).iterrows():
            org_name = str(row['ORG_NM'])
            rows.append([str(row['RO_ID']), org_name[:25], str(row['LATEST_STAGE_NM']), str(int(row['minutes_stuck']))])
        
        self._draw_zebra_table(pdf, headers, rows, [25, 65, 60, 30])
        pdf.ln(10)

        # --- D. MARKET IMPACT TABLE ---
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Market Correlation & SLA Impact", ln=True)
        
        headers = ["Market", "Failed ROs", "Stuck ROs", "Success %"]
        rows = []
        for _, row in market_df.sort_values('SCS_PERCENT', ascending=True).head(5).iterrows():
            rows.append([str(row['CNT_STATE']), str(row['failed_ros']), str(row['stuck_ros']), f"{row['SCS_PERCENT']}%"])
        
        self._draw_zebra_table(pdf, headers, rows, [40, 50, 50, 40])
        
        # Footer
        pdf.set_y(-25)
        pdf.set_font("Arial", "I", 8)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 10, "Confidential - RosterIQ Proprietary Intelligence Report", align='C')

        return pdf.output(dest="S").encode("latin-1") if isinstance(pdf.output(dest="S"), str) else pdf.output(dest="S")

    def _draw_zebra_table(self, pdf, headers, rows, widths):
        """Helper to draw professional zebra-striped tables."""
        # Header
        pdf.set_fill_color(40, 70, 120) # Blue header
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B", 10)
        for i, h in enumerate(headers):
            pdf.cell(widths[i], 10, h, border=0, fill=True)
        pdf.ln()
        
        # Rows
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 9)
        for i, row in enumerate(rows):
            fill = (i % 2 == 1)
            pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
            for j, val in enumerate(row):
                pdf.cell(widths[j], 8, val, border=0, fill=True)
            pdf.ln()

    def generate_pipeline_health_report(self):
        """Standard Markdown summary for chat window."""
        health_df = self.query_tool.derive_metrics("health")
        stuck_df = self.query_tool.derive_metrics("stuck_duration")
        market_df = self.engine.market_pipeline_correlation()
        avg_health = health_df['composite_health_score'].mean()
        
        report = f"""
# 📋 Provider Roster Health Summary
**Health Score:** `{avg_health:.2f} / 1.0` | **Stuck ROs:** `{len(stuck_df)}`

**Top Bottleneck:** {stuck_df.iloc[0]['RO_ID'] if not stuck_df.empty else 'None'}
**Critical Markets:** {', '.join(market_df[market_df['SCS_PERCENT'] < 95.0]['CNT_STATE'].unique().tolist()[:5])}

*Run 'Export PDF' for the high-fidelity diagnostic report.*
"""
        return report