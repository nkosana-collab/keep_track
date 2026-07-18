import pandas as pd

def make_payment(date,customer,amount):
    
    # Define the new row data as a DataFrame.
    new_payment = {
        'date': [date],
        'customer': [customer],
        'amount': [amount]
    }
    new_data_frame = pd.DataFrame(new_payment)

    # Append to the existing file.
    new_data_frame.to_csv('./tables/payments.csv', mode='a', index=False, header=False)

    # Update the credits.csv
    decreament_credit(customer, amount)



def decreament_credit(customer,amount):
    credits = pd.read_csv("./tables/credits.csv")

    credit_account = credits[
        (credits["customer"] == customer)
                    ]
    
    current_amount = credit_account["amount"].iloc[0]
    if current_amount - amount <= 0:
        credits.loc[
                credits["customer"] == customer,
                "amount",
            ] = 0
        
        credits.loc[
                credits["customer"] == customer,
                "status",
            ] = "settled"
        
    else:
        credits.loc[
                credits["customer"] == customer,
                "amount"
            ] -= amount
        
    credits.to_csv("./tables/credits.csv", index=False)

make_payment("2026-07-07", "technical",300)