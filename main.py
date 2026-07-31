import re
import sys

# from model.customer import Customer
from services.make_payment import make_payment
from services.report import Report
from services.update_credits import update_credit
from model.customer import Customer

command = sys.argv

if len(command) == 2:

    pattern = r"^\d{4}-\d{2}-\d{2}$"

    if re.match(pattern, command[1]):
        update_credit(command[1])
    else:
        customer = Customer(command[1])
        customer.generate_report()
        

elif len(command) == 3:

    start_date = command[1]
    end_date = command[2]

    report = Report(start_date, end_date)
    
    report.generate_report()

elif len(command) == 4:
    
    date = command[1]
    customer = command[2]
    amount = int(command[3])

    make_payment(date, customer, amount)

else: 
    print("Inavalid command!!")