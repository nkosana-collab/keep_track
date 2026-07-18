import pandas as pd

class Report():
    def __init__(self, start_date, end_date):

        self.start_date = start_date
        self.end_date = end_date



    def get_sales(self):
        
        df = pd.read_csv("./tables/daily_sales.csv", parse_dates=["date"])

        mask = (df["date"] >= self.start_date) & (df["date"] <= self.end_date)
        df = df[mask]

        df["line_total"] = df["quantity"] * df["amount"]

        totals = df.groupby("method")["line_total"].sum()

        return {
            "cash_sales": int(totals.get("cash", 0)),
            "credit_sales": int(totals.get("credit", 0)),
            "eft_sales": int(totals.get("eft", 0)),
        }
    


    def get_credits(self):

        df = pd.read_csv("./tables/credits.csv")
        df = df[df["status"] == "active"]

        balances = {
            row["customer"]: int(row["amount"])
            for row in df.to_dict("records")
        }
        total = int(df["amount"].sum())

        return balances, total
        



    def get_expenses(self):
    
        df = pd.read_csv("./tables/expenses.csv", parse_dates=["date"])

        mask = (df["date"] >= self.start_date) & (df["date"] <= self.end_date)
        df = df[mask]

        return int(df["amount"].sum())
    

        
        
    def generate_report(self):
        
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )

        # 1. Pull data from your methods.
        sales = self.get_sales()
        balances, credit_total = self.get_credits()
        expenses = self.get_expenses()

        # 2. Derived figures for the summary table.
        cash_sales = sales["cash_sales"]
        credit_sales = sales["credit_sales"]
        eft_sales = sales["eft_sales"]
        gross_total = cash_sales + credit_sales + eft_sales
        net_total = gross_total - expenses

        # 3. Document skeleton.
        doc = SimpleDocTemplate(
            "report.pdf", pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        story = []

        plain_style = TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ])

        # 4. Title + period.
        story.append(Paragraph("Business Report", styles["Heading1"]))
        story.append(Paragraph(
            f"Period: {self.start_date} to {self.end_date}", styles["Normal"]
        ))
        story.append(Spacer(1, 12))

        # 5. Credits table — reshape the balances dict into rows.
        story.append(Paragraph("Active Credits", styles["Heading2"]))
        credit_rows = [["Customer", "Balance"]]
        for customer, balance in balances.items():
            credit_rows.append([customer, balance])
        credit_rows.append(["Total", credit_total])

        credit_table = Table(credit_rows, hAlign="LEFT",
                            colWidths=[80 * mm, 40 * mm])
        credit_table.setStyle(plain_style)
        story.append(credit_table)
        story.append(Spacer(1, 20))

        # 6. Summary table — fixed rows, per the spec.
        story.append(Paragraph("Summary", styles["Heading2"]))
        summary_rows = [
            ["Type", "Total"],
            ["Credit_sales", credit_sales],
            ["Cash_sales", cash_sales],
            ["EFT_sales", eft_sales],
            ["Gross_total", gross_total],
            ["Expenses", expenses],
            ["Net_total", net_total],
        ]
        summary_table = Table(summary_rows, hAlign="LEFT",
                            colWidths=[80 * mm, 40 * mm])
        summary_table.setStyle(plain_style)
        story.append(summary_table)

        # 7. Render.
        doc.build(story)