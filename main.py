import sys
# from model.customer import Customer
from services.make_payment import make_payment
from services.report import Report
from services.update_credits import update_credit


command = sys.argv

if len(command) == 2:

    update_credit(command[1])

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