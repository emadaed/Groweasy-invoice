import random

def random_invoice_number():
    return f"INV-{random.randint(10000, 99999)}"
