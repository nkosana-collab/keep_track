import pandas as pd

def update_credit(date):

    sales = pd.read_csv("./tables/daily_sales.csv")
    credits = pd.read_csv("./tables/credits.csv")

    credit_sales = sales[
        (sales["method"] == "credit") &
        (sales["date"] == date)
    ]

    for _, sale in credit_sales.iterrows():

        customer = sale["customer"]
        amount = sale["amount"] * sale['quantity']

        if customer in credits["customer"].values:
            credits.loc[
                credits["customer"] == customer,
                "amount"
            ] += amount
        else:
            credits = pd.concat([
                credits,
                pd.DataFrame({
                    "customer": [customer],
                    "amount": [amount],
                    "status": ["active"]
                })
            ], ignore_index=True)

    credits.to_csv("./tables/credits.csv", index=False)

update_credit("2026-07-07")