import os
import json

config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def read_config():
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config
config = read_config()

ACCOUNT_BALANCE = config["ACCOUNT_BALANCES"][0]
ORDER_PERCENTAGE = config["ORDER_PERCENTAGE"]

testing = False

def calculate_quantity(cost_per_contract):
    # 'order_size_for_account' represents the percentage of the account you want to spend on each order.
    order_threshold = ACCOUNT_BALANCE * ORDER_PERCENTAGE
    order_cost = cost_per_contract * 100

    order_quantity = order_threshold / order_cost
    #print(f"Order quantity before processing: {order_quantity}")

    if order_quantity > 1.0:
        # Round down to the nearest whole number
        order_quantity = int(order_quantity)
        # Check if the rounded down quantity exceeds the order threshold
        if (order_quantity * order_cost) > order_threshold:
            # If it does, reduce the quantity by one
            order_quantity -= 1
        quantity = order_quantity

    elif order_quantity < 1.0:
        # One contract exceeds the order threshold, so use one contract
        quantity = 1

    return quantity

if testing:
    bid = 0.13
    quantity = calculate_quantity(bid)
    print(f"quant: {quantity}")
    cost = quantity * (bid * 100)
    print(f"cost: ${cost:,.2f}")  # Formats the cost as currency with 2 decimal places
    percentage_check = cost / ACCOUNT_BALANCE * 100  # Multiply by 100 to convert to percentage
    print(f"Percentage check: {percentage_check:.3f}%")