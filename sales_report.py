#!/usr/bin/env python3
"""
sales_report.py

Generates a PDF sales report for a given date range from daily_sales.csv.

The report includes:
  - A heading stating the document is a report
  - The time frame covered
  - A bar graph showing the percentage contributed by each payment method
  - The amount contributed by each payment method
  - The gross total
  - The net total (gross total minus the credit amount)

Usage:
    python sales_report.py --start 2026-07-07 --end 2026-07-13
    python sales_report.py --start 2026-07-07 --end 2026-07-13 --csv daily_sales.csv --output report.pdf

    If --start/--end are not supplied, the script will prompt for them
    interactively.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend, needed for headless PDF generation
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a sales report PDF for a date range.")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--csv", default="daily_sales.csv", help="Path to the daily_sales.csv file")
    parser.add_argument("--output", default="sales_report.pdf", help="Path for the output PDF")
    return parser.parse_args()


def get_date_range(args):
    start = args.start or input("Enter start date (YYYY-MM-DD): ").strip()
    end = args.end or input("Enter end date (YYYY-MM-DD): ").strip()
    try:
        start_date = pd.to_datetime(start)
        end_date = pd.to_datetime(end)
    except ValueError as exc:
        sys.exit(f"Could not parse date: {exc}")
    if start_date > end_date:
        sys.exit("Start date must be on or before the end date.")
    return start_date, end_date


def load_data(csv_path, start_date, end_date):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        sys.exit(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    mask = (df["date"] >= start_date) & (df["date"] <= end_date)
    filtered = df.loc[mask].copy()

    if filtered.empty:
        sys.exit("No sales records found in the given date range.")

    return filtered


def build_summary(df):
    by_method = df.groupby("method")["amount"].sum().sort_values(ascending=False)
    gross_total = df["amount"].sum()
    credit_total = by_method.get("credit", 0)
    net_total = gross_total - credit_total
    percentages = (by_method / gross_total * 100).round(1)
    return by_method, percentages, gross_total, credit_total, net_total


def make_bar_chart(percentages, image_path):
    fig, ax = plt.subplots(figsize=(6, 3.5))
    methods = [m.upper() for m in percentages.index]
    bars = ax.bar(methods, percentages.values, color=["#2E86AB", "#A23B72", "#F18F01"])

    ax.set_ylabel("Percentage of Gross Total (%)")
    ax.set_title("Contribution by Payment Method")
    ax.set_ylim(0, max(percentages.values) * 1.2)

    for bar, pct in zip(bars, percentages.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(percentages.values) * 0.02,
            f"{pct}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    fig.tight_layout()
    fig.savefig(image_path, dpi=200)
    plt.close(fig)


def build_pdf(output_path, start_date, end_date, by_method, percentages,
              gross_total, credit_total, net_total, chart_path):
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                             topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=22, spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontSize=12,
        textColor=colors.HexColor("#555555"), spaceAfter=18
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8
    )

    story = []

    # Heading
    story.append(Paragraph("Sales Report", title_style))

    # Time frame
    date_fmt = "%d %B %Y"
    story.append(Paragraph(
        f"Reporting period: {start_date.strftime(date_fmt)} &ndash; {end_date.strftime(date_fmt)}",
        subtitle_style,
    ))

    # Bar graph
    story.append(Paragraph("Payment Method Contribution", section_style))
    story.append(Image(str(chart_path), width=6 * inch, height=3.5 * inch))
    story.append(Spacer(1, 12))

    # Amount per payment method table
    story.append(Paragraph("Amount by Payment Method", section_style))
    table_data = [["Payment Method", "Amount (R)", "% of Gross Total"]]
    for method, amount in by_method.items():
        table_data.append([method.upper(), f"{amount:,.2f}", f"{percentages[method]}%"])

    method_table = Table(table_data, colWidths=[2.2 * inch, 2 * inch, 2 * inch])
    method_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(method_table)
    story.append(Spacer(1, 20))

    # Totals table
    story.append(Paragraph("Totals", section_style))
    totals_data = [
        ["Gross Total", f"R {gross_total:,.2f}"],
        ["Credit Amount", f"R {credit_total:,.2f}"],
        ["Net Total (Gross - Credit)", f"R {net_total:,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[3.2 * inch, 3 * inch])
    totals_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFEFEF")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(totals_table)

    doc.build(story)


def main():
    args = parse_args()
    start_date, end_date = get_date_range(args)
    df = load_data(args.csv, start_date, end_date)
    by_method, percentages, gross_total, credit_total, net_total = build_summary(df)

    chart_path = Path(args.output).with_suffix(".chart.png")
    make_bar_chart(percentages, chart_path)

    build_pdf(args.output, start_date, end_date, by_method, percentages,
              gross_total, credit_total, net_total, chart_path)

    chart_path.unlink(missing_ok=True)  # clean up temp chart image

    print(f"Report generated: {args.output}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Gross total: R {gross_total:,.2f}")
    print(f"Net total:   R {net_total:,.2f}")


if __name__ == "__main__":
    main()