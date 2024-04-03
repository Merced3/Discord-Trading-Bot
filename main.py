import requests
import sys
import discord
from discord import Intents
from discord.ext import commands
from discord.ui import View, Button
import pytz
import os
from twilio.rest import Client
import cred
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
import text_classification
from buy_classification import extract_info_from_message
from sell_classification import classify_sell_message
import inspect

real_money_activated = False

paper_trading_contract_quantity = 10
real_money_contract_quantity = 1

if real_money_activated:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}"
    }
else:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}"
    }

last_trade_info = {
    'ticker_symbol': '',
    'strike': '',
    'cp': '',
    'expiration_date': '',
    'quantity': 0
}

class MyView(View):
    def __init__(self, button_data):
        super().__init__()
        for index, data in enumerate(button_data):
            self.add_item(Button(style=data["style"], label=data["label"], custom_id=str(index)))

async def create_view(button_data):
    view = MyView(button_data)
    return view

async def print_discord(message1, message2=None, button_data=None):

    message_channel = bot.get_channel(cred.DISCORD_CHANNEL_ID)
    message_channel_id = message_channel.id
    if message_channel_id:
        message_channel = bot.get_channel(message_channel_id)
        
    view = await create_view(button_data) if button_data else None

    if message2:
        print(message1)
        if message2:
            await message_channel.send(content=message2, view=view) if button_data else await message_channel.send(message2)
        #await send_sms(message2)
    else:
        print(message1)
        if message1:
            await message_channel.send(content=message1, view=view) if button_data else await message_channel.send(message1)
        #await send_sms(message1)

    if message1 is None:
        print(f"This function was called from line {inspect.currentframe().f_back.f_lineno}")

async def Stop_script(msg_str, str_stopException):
    await print_discord(msg_str)
    await bot.close()
    raise StopScriptException(str_stopException)

async def send_sms(body_message):
    # Send total profits using Twilio
    account_sid = cred.TWILIO_ACCOUNT_SID
    auth_token = cred.TWILIO_AUTH_TOKEN

    def _send_sms():
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body_message,
            from_=cred.TWILIO_PHONE_NUMBER,
            to=cred.MY_PHONE_NUMBER
        )
        return message.sid

    message_sid = await asyncio.to_thread(_send_sms)
    return message_sid

async def submit_option_order(symbol, strike, option_type, bid, expiration_date, quantity, side, order_type):
    if real_money_activated:
        order_url = f"{cred.TRADIER_BROKERAGE_BASE_URL}accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/orders"
        headers = {
            "Authorization": f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",
            "Accept": "application/json"
        }
    else:
        order_url = f"{cred.TRADIER_SANDBOX_BASE_URL}accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/orders"
        headers = {
            "Authorization": f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}",
            "Accept": "application/json"
        }
    
    expiration_date = datetime.strptime(expiration_date, "%Y%m%d").strftime("%y%m%d")
    option_symbol = f"{symbol}{expiration_date}{option_type[0].upper()}{int(float(strike) * 1000):08d}"


    order_type = 'market' if bid is None or bid == 'not specified' else 'limit'

    payload = {
        "class": "option",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "type": order_type,
        "duration": "gtc",
        "option_symbol": option_symbol,
    }

    if order_type == 'limit':
        payload["price"] = bid

    print(f"Submitting order with payload: {payload}")  # Debug print

    response = requests.post(order_url, headers=headers, data=payload)
    print(f"response: {response}")

    if response.status_code == 200:
        response_data = response.json()
        if 'order' in response_data:
            await print_discord("Order Submitted", f"{symbol} Order Pending")
            result = {'order_id': response_data['order']['id']}
            if bid and bid != 'not specified':
                result['total_value'] = float(bid) * quantity * 100
            return result
        elif 'error' in response_data['errors']:
            #getting account balance
            if real_money_activated:
                endpoint = f'https://api.tradier.com/v1/accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/balances'
                headers = {'Authorization': f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",'Accept': 'application/json'}
            else:
                endpoint = f'https://api.tradier.com/v1/accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/balances'
                headers = {'Authorization': f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}",'Accept': 'application/json'}
            response = requests.get(endpoint,headers=headers)
            json_response = response.json()
            
            if 'cash' in json_response['balances']:
                account_buying_power = json_response['balances']['cash']['cash_available']
                order_cost = float(bid) * quantity * 100 if bid and bid != 'not specified' else 0
                await print_discord(f"\nOrder submission failed. Settled Funds too low: ${account_buying_power}. Order Cost: ${order_cost}")
            else:
                await print_discord(f"\nOrder submission failed. Settled Funds not available. Account Response content: {response.content}")
        else:
            await print_discord(f"\nOrder submission failed. Response content: {response.content}")
    else:
        await print_discord(f"\nOrder submission failed. Response status code: {response.status_code}", f"Order failed, response content: {response.content}")
        return None

async def get_order_status(order_id, b_s, quantity, ticker_symbol, cp, message):
    if real_money_activated:
        order_url = f"{cred.TRADIER_BROKERAGE_BASE_URL}accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/orders/{order_id}"
        headers = {"Authorization": f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}", "Accept": "application/json"}
    else:
        order_url = f"{cred.TRADIER_SANDBOX_BASE_URL}accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/orders/{order_id}"
        headers = {"Authorization": f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}", "Accept": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        loading_chars = "|/-\\"
        i = 0
        status = 'open'  # Initialize status outside the loop
        while status == 'open':
            async with session.get(order_url, headers=headers) as response:
                response_content = await response.text()
                print(response_content)  # Add this line to print the response content

                try:
                    response_json = await response.json()
                except Exception as e:
                    print("Error parsing JSON:", e)
                    continue
                order = response_json['order']
                status = order['status']

                sys.stdout.write("\033[K")  # Clear the current line
                sys.stdout.write(f"\r{status} {loading_chars[i % len(loading_chars)]}")
                sys.stdout.flush()

                if status == 'filled':
                    print("")  # Print a newline to move to the next line after the order is filled
                    order_price = float(order.get('avg_fill_price', 0))
                    order_quantity = int(order.get('quantity', 0))

                    if b_s == "buy":
                        total_investment = order_price * order_quantity * 100
                        _message_ = f"Buy Order fulfilled: {order_price} Bought {order_quantity} {ticker_symbol} {cp} contracts. Total investment: ${total_investment:.2f}"
                    else:
                        total_value = order_price * order_quantity * 100
                        _message_ = f"Sell Order fulfilled: {order_price} Sold {order_quantity} {ticker_symbol} {cp} contracts. Total value: ${total_value:.2f}"

                    await print_discord(_message_)#, message=message)
                    return
                elif status == 'canceled':
                    print("")
                    await print_discord(f"{ticker_symbol} Order Canceled")#, message=message)
                    return
            i += 1



intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}\n")
    if real_money_activated:
        await print_discord("Real Money Activated")
    else:
        await print_discord("Paper Trading Activated")

    bot.loop.create_task(market_hours_check())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # Ignore messages sent by the bot itself
    if message.channel.id == cred.DISCORD_CHANNEL_ID:
        print("__________________________________________________________________________________________________________________________________________")
        print(f"Received message from 🚨-trades: {message.content}")

        action = text_classification.predict_action(text_classification.clf, text_classification.vectorizer, message.content)
        print(f"Predicting most likely action: {action}\n")

        if action in ["buy", "sell"]:
            if action == "buy":
                info = extract_info_from_message(message.content)
                print(f"Info returned: {info}")
                cp, bid, expiration_date, quantity, strike, ticker_symbol = info
            else:  # If the action is "sell", use the last_trade_info dictionary
                cp = last_trade_info['cp']
                bid = None
                expiration_date = last_trade_info['expiration_date']
                quantity = last_trade_info['quantity']
                strike = last_trade_info['strike']
                ticker_symbol = last_trade_info['ticker_symbol']

            print(f"\nmain.py ticker_symbol: {ticker_symbol}")
            print(f"main.py strike: {strike}")
            print(f"main.py cp: {cp}")
            print(f"main.py bid: {bid}")
            print(f"main.py expiration_date: {expiration_date}")
            print(f"main.py quantity: {quantity}\n")

            if ticker_symbol == "not specified" or strike == "not specified" or cp == "not specified":
                await print_discord("Canceled the buy, not enough information was disclosed")#, message=message)
            else:
                if action == "buy":



                    
                    side = "buy_to_open"
                    order_type = "limit" if bid else "market"

                    current_datetime = datetime.now()
                    if expiration_date == "not specified":  # default expiration is whenever the script is run
                        expiration_date = current_datetime.strftime("%Y%m%d")  # 20230326 for example
                    elif expiration_date[:-3].isdigit() and expiration_date[-3:] == "dte": #if 1dte, 2dte... is true
                        number_of_days = int(expiration_date[:-3])
                        expiration_date_str = current_datetime + timedelta(days=number_of_days)
                        expiration_date = expiration_date_str.strftime("%Y%m%d")
                        expiration_day_of_week = expiration_date_str.weekday()  # Monday is 0 and Sunday is 6
                        # Check if the expiration date is a Saturday (5) or Sunday (6)
                        if expiration_day_of_week in [5, 6]:
                            await print_discord(f"Canceled the buy, Invalid expiration date (weekend): {expiration_date}")
                            return
                    else:
                        await print_discord(f"Canceled the buy, Invalid expiration date: {expiration_date}")
                        return

                    if quantity == "not specified":
                        if real_money_activated:
                            quantity = real_money_contract_quantity  # default amount of contracts
                        else:
                            quantity = paper_trading_contract_quantity






                    last_trade_info['ticker_symbol'] = ticker_symbol
                    last_trade_info['strike'] = strike
                    last_trade_info['cp'] = cp
                    last_trade_info['expiration_date'] = expiration_date
                    last_trade_info['quantity'] = quantity

                    order_result = await submit_option_order(ticker_symbol, strike, cp, bid, expiration_date, quantity, side, order_type)
                    if order_result:
                        await get_order_status(order_result['order_id'], "buy", quantity, ticker_symbol, cp, message=message)
                    
                else: #sell
                    side = "sell_to_close"
                    order_type = "market"
                    
                    if quantity > 1:
                        sell_percentage = classify_sell_message(message.content)
                        print(f"Predicted sell percentage: {sell_percentage} for message: {message.content}")
                        # Calculate the quantity based on the sell_percentage
                        sell_percentage_float = float(sell_percentage.strip('%')) / 100
                        quantity_to_sell = int(quantity * sell_percentage_float)

                        # Update the remaining quantity in last_trade_info
                        last_trade_info['quantity'] -= quantity_to_sell
                    else: #since quantity is 1, theres no point in dividing it
                        quantity_to_sell = quantity

                    order_result = await submit_option_order(ticker_symbol, strike, cp, bid, expiration_date, quantity_to_sell, side, order_type)
                    if order_result:
                        await get_order_status(order_result['order_id'], "sell", quantity, ticker_symbol, cp, message=message)
                
        elif action == "do_nothing":
            await print_discord("Action: doing nothing, waiting for new message")#, message=message)
            
    await bot.process_commands(message)

class StopScriptException(Exception):
    pass

async def market_hours_check():
    market_open_printed = False
    while True:
        now = datetime.now(pytz.timezone("US/Eastern"))

        if now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.hour >= 16:
            market_open_printed = False
            # Calculate time until market open
            market_open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
            if now.hour >= 16:
                market_open_time += timedelta(days=1)
            time_until_open = market_open_time - now
            hours, remainder = divmod(time_until_open.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"Market is closed. Waiting {hours:02}:{minutes:02}:{seconds:02} until the market opens.")
            await asyncio.sleep(time_until_open.total_seconds())
        else:
            if not market_open_printed:
                # Getting account balance
                if real_money_activated:
                    endpoint = f'https://api.tradier.com/v1/accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/balances'
                    headers = {'Authorization': f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",'Accept': 'application/json'}
                #else:
                    #endpoint = f'https://api.tradier.com/v1/accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/balances'
                    #headers = {'Authorization': f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}",'Accept': 'application/json'}
                
                response = requests.get(endpoint, headers=headers)
                
                print(response)
                try:
                    response.raise_for_status()  # Raise exception for non-OK responses
                    json_response = response.json()

                    if real_money_activated:
                        if 'cash' in json_response.get('balances', {}):
                            account_buying_power = json_response['balances']['cash']['cash_available']
                            await print_discord(f"\nMarket is OPEN! Ready BP Today: ${account_buying_power}")
                            market_open_printed = True
                        else:
                            print("Cash balance not found in JSON response for real money account.")
                    """
                    else:
                        if 'option_bp' in json_response.get('balances', {}):
                            account_buying_power = json_response['balances']['total_cash']  # Change this to the correct key for paper trading, sandbox paper trading Option B.P
                            await print_discord(f"\nMarket is OPEN! Ready BP Today: ${account_buying_power}")
                            market_open_printed = True
                        else:
                            print("Option buying power balance not found in JSON response for paper trading account.")
                    
                except requests.exceptions.HTTPError as http_err:
                    print(f"HTTP error occurred: {http_err}")
                """
                except json.decoder.JSONDecodeError as json_err:
                    print(f"JSON decode error occurred: {json_err}")
                
            await asyncio.sleep(5)

if __name__ == "__main__":
    while True:
        try:
            bot.run(cred.DISCORD_TOKEN)
        except Exception as e:
            print(f"Exception occurred: {e}")
            time.sleep(60)  # Pause for a minute before restarting the bot