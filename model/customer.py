import pandas as pd


class Customer:
    def __init__(self, name):
        self.name = name

    def get_credit_record(self):
        """
        Look up this customer's row in credits.csv and return the
        balance they currently owe.
        """
        credits = pd.read_csv("./tables/credits.csv")

        credit_account = credits[credits["customer"] == self.name]

        if credit_account.empty:
            raise ValueError(f"No credit record found for customer '{self.name}'")

        balance_due = credit_account["amount"].iloc[0]
        return balance_due

    def get_credit_sales(self):
        """
        Starting from this customer's most recent sale, walk backwards
        through their credit-method sales in daily_sales.csv, accumulating
        line totals (quantity * amount) until they add up to the
        outstanding balance from credits.csv.

        Returns (sales_df, balance_due) where sales_df holds just the
        rows that make up the balance, sorted oldest -> newest, with a
        `line_total` column added.
        """
        balance_due = self.get_credit_record()

        sales = pd.read_csv("./tables/daily_sales.csv", parse_dates=["date"])

        customer_credit_sales = sales[
            (sales["customer"] == self.name) &
            (sales["method"] == "credit")
        ].copy()

        customer_credit_sales["line_total"] = (
            customer_credit_sales["quantity"] * customer_credit_sales["amount"]
        )

        # Latest sale first, so we walk backwards in time.
        customer_credit_sales = customer_credit_sales.sort_values(
            "date", ascending=False
        )

        selected_rows = []
        running_total = 0
        if balance_due > 0:
            for _, row in customer_credit_sales.iterrows():
                selected_rows.append(row)
                running_total += row["line_total"]
                if running_total >= balance_due:
                    break

        result_df = pd.DataFrame(selected_rows, columns=customer_credit_sales.columns)

        if not result_df.empty:
            # Chronological order for the report.
            result_df = result_df.sort_values("date").reset_index(drop=True)

        return result_df, balance_due

    def generate_report(self):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )

        sales_df, balance_due = self.get_credit_sales()

        doc = SimpleDocTemplate(
            f"{self.name}_credit_report.pdf", pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(self.name, styles["Heading1"]))
        story.append(Spacer(1, 12))

        table_rows = [["Date", "Size", "Quantity", "Amount"]]
        for _, row in sales_df.iterrows():
            date_value = row["date"]
            date_str = (
                date_value.strftime("%Y-%m-%d")
                if hasattr(date_value, "strftime")
                else str(date_value)
            )
            table_rows.append([
                date_str,
                row["size"],
                row["quantity"],
                row["amount"],
            ])
        table_rows.append(["", "", "Balance due", balance_due])

        style = TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ])
        table = Table(table_rows, hAlign="LEFT",
                      colWidths=[35 * mm, 25 * mm, 25 * mm, 35 * mm])
        table.setStyle(style)
        story.append(table)

        doc.build(story)
