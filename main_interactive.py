import requests
import sys
import discord
from discord.ext import commands, tasks
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
from quantity_handler import calculate_quantity
import inspect
import re

real_money_activated = False

real_money_contract_quantity = 1
paper_trading_contract_quantity = 10

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

message_with_buttons = None
button_contract_info = {}
total_sold_percentage = 0

message_ids_dict = {}
Today_Start_Balance = ""
Today_End_Balance = ""


intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class MyView(View):
    def __init__(self, button_data):
        super().__init__(timeout=None)
        for data in button_data:
            self.add_item(Button(style=data["style"], label=data["label"], custom_id=data["custom_id"]))
            
def calculate_profit_percentage(message):
    # Extract buy details
    buy_pattern = r"\*\*Buy Order Completed\*\*\n\*\*Price:\*\* \$(\d+\.\d+)\n\*\*Quantity:\*\* (\d+) contracts \((.+?)\)\n\*\*Total Investment:\*\* \$(\d+\.\d+)\n-----"
    buy_match = re.search(buy_pattern, message)
    if not buy_match:
        return "Invalid Buy Details"
    buy_price = float(buy_match.group(1))
    buy_quantity = int(buy_match.group(2))
    cp_value = buy_match.group(3)  # New extraction for cp
    total_investment = float(buy_match.group(4))
    
    # Extract sell details
    sell_pattern = r"Sold (\d+) .+? contracts for \$(\d+\.\d+), Fill: (\d+\.\d+)"
    sell_matches = re.findall(sell_pattern, message)
    if not sell_matches:
        return "Invalid Sell Details"
    # Calculate the total sales
    total_sales = sum([float(sale[1]) for sale in sell_matches])
    # Calculate average bid
    total_contracts_sold = sum([int(sale[0]) for sale in sell_matches])
    total_bid_value = sum([int(sale[0]) * float(sale[2]) for sale in sell_matches])
    avg_bid = total_bid_value / total_contracts_sold
    # Calculate profit or loss
    profit_or_loss = total_sales - total_investment
    profit_or_loss_percentage = (profit_or_loss / total_investment) * 100
    if profit_or_loss_percentage >= 0: 
        #if positive, how do i calculate average bid?
        return f"\n\n**AVG BID:**    ${avg_bid:.3f}\n**TOTAL:**    ${profit_or_loss:.2f}✅\n**PERCENT:**    {profit_or_loss_percentage:.2f}%"

    else: 
        # if negitive
        return f"\n\n**AVG BID:**    ${avg_bid:.3f}\n**TOTAL:**    ${profit_or_loss:.2f}❌\n**PERCENT:**    {profit_or_loss_percentage:.2f}%"

async def create_view(button_data):
    view = MyView(button_data)
    return view

async def print_discord(message1, message2=None, button_data=None, delete_last_message=None):

    message_channel = bot.get_channel(cred.DISCORD_CHANNEL_ID)
    message_channel_id = message_channel.id
    if message_channel_id:
        message_channel = bot.get_channel(message_channel_id)

    if delete_last_message:
        async for old_message in message_channel.history(limit=1):
            await old_message.delete()
        
    view = await create_view(button_data) if button_data else None

    sent_message = None  # initialize sent_message as None
    if message2:
        sent_message = await message_channel.send(content=message2, view=view) if button_data else await message_channel.send(message2)
    else:
        sent_message = await message_channel.send(content=message1, view=view) if button_data else await message_channel.send(message1)

    if message1 is None:
        print(f"This function was called from line {inspect.currentframe().f_back.f_lineno}")
    else:
        print(message1)
    
    return sent_message  # return the sent message

def generate_unique_key(ticker_symbol, cp, strike, expiration_date, timestamp):
    return f"{ticker_symbol}-{cp}-{strike}-{expiration_date}-{timestamp}"

def generate_timestamp():
    return datetime.now().strftime('%Y%m%d%H%M%S%f')

def generate_buttons(num_contracts):
    if num_contracts >= 10:
        button_percentages = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    else:
        button_percentages = []
        # Calculate the percentage per button
        one_contract_percentage = 100 / num_contracts
        
        # Calculate the number of buttons needed based on num_contracts
        number_of_buttons = num_contracts
        
        # Assign percentage text for buttons
        i=1
        for _ in range(number_of_buttons):
            # Append the calculated percentage to button_percentages
            button_percentages.append(round(one_contract_percentage * i))
            i=i+1
    return button_percentages

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

    print(f"Submitting order with payload: {payload}") #---------------------------------------------------------------------

    response = requests.post(order_url, headers=headers, data=payload)
    print(f"response: {response}")

    if response.status_code == 200:
        response_data = response.json()
        if 'order' in response_data:
            await print_discord("Order Submitted", f"{symbol} Buy Order Pending" if side=="buy_to_open" else "Sell Order Pending")
            result = {'order_id': response_data['order']['id']}
            if bid and bid != 'not specified':
                result['total_value'] = float(bid) * quantity * 100
            return result
        elif 'error' in response_data['errors']:
            #getting account balance
            if real_money_activated:
                endpoint = f'{cred.TRADIER_BROKERAGE_BASE_URL}v1/accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/balances'
                headers = {'Authorization': f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",'Accept': 'application/json'}
            else:
                endpoint = f'{cred.TRADIER_SANDBOX_BASE_URL}v1/accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/balances'
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
        if response.status_code == 500:
            error_message = "500 errors typically mean that something isn't working properly with Tradier API. Please let us know by emailing techsupport@tradier.com."
        else:
            error_message = f"Order failed, response content: {response.content}"

        await print_discord(f"\nOrder submission failed. Response status code: {response.status_code}", error_message)
        return None


async def get_order_status(order_id, b_s, ticker_symbol, cp, strike, expiration_date, order_timestamp):
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
                    unique_order_key = generate_unique_key(ticker_symbol, cp, strike, expiration_date, order_timestamp)
                    order_price = float(order.get('avg_fill_price', 0))
                    order_quantity = int(order.get('quantity', 0))

                    if b_s == "buy":
                        
                        total_investment = order_price * order_quantity * 100
                        message_with_buttons_obj = await sell_button_generation(ticker_symbol, order_quantity, cp, strike, expiration_date, order_timestamp)
                        global message_with_buttons
                        message_with_buttons = message_with_buttons_obj
                        _message_ = f"**Buy Order Completed**\n**Price:** ${order_price:.2f}\n**Quantity:** {order_quantity} contracts ({cp})\n**Total Investment:** ${total_investment:.2f}\n-----"
                        
                        message_obj = await print_discord(_message_)
                        message_ids_dict[unique_order_key] = message_obj.id # Save message ID for this specific order
                        print(f"Saved Message ID {message_obj.id} for {unique_order_key}. Current dictionary state: {message_ids_dict}") #this dictionary holds all the trades message ID's, those Message ID holds all the info to that specific trade.
                    else: #sell
                        total_value = order_price * order_quantity * 100
                        _message_ = f"Sold {order_quantity} {ticker_symbol} contracts for ${total_value:.2f}, Fill: {order_price}"

                        message_channel = bot.get_channel(cred.DISCORD_CHANNEL_ID)
                        message_channel_id = message_channel.id
                        if message_channel_id:
                            message_channel = bot.get_channel(message_channel_id)

                        if unique_order_key in message_ids_dict:
                            original_msg_id = message_ids_dict[unique_order_key]
                            original_msg = await message_channel.fetch_message(original_msg_id)
                            updated_content = original_msg.content + "\n" + _message_
                            await original_msg.edit(content=updated_content)
                            async for old_message in message_channel.history(limit=1):
                                await old_message.delete()
                        else:
                            print(f"Message ID for order {unique_order_key} not found in dictionary. Dictionary contents:\n{message_ids_dict}")
                    
                    return
                elif status == 'canceled':
                    print("")
                    await print_discord(f"{ticker_symbol} Order Canceled", delete_last_message=True)#, message=message)
                    return status
            i += 1










async def get_account_balance(is_real_money, bp=None):
    if is_real_money:
        endpoint = f'{cred.TRADIER_BROKERAGE_BASE_URL}accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/balances'
        headers = {'Authorization': f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",'Accept': 'application/json'}
    else:
        endpoint = f'{cred.TRADIER_SANDBOX_BASE_URL}accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/balances'
        headers = {'Authorization': f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}",'Accept': 'application/json'}

    response = requests.get(endpoint, headers=headers)
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()  # Raises a HTTPError if the HTTP request returned an unsuccessful status code

        try:
            json_response = response.json()
            # Assuming 'balances' is a top-level key in the JSON response:
            balances = json_response.get('balances', {})
            print(balances)
            if is_real_money and bp is None:
                print("is_real_money and bp is None")
                return balances['total_cash']
            elif is_real_money==False:
                print("is_real_money==False")
                return balances['margin']['option_buying_power']
            elif bp is not None and True:
                print("bp is not None and True")
                return balances['cash']['cash_available']
        except json.decoder.JSONDecodeError as json_err:
            # Print response text to inspect what was returned
            print(f"JSON decode error occurred: {json_err}")
            print(f"Response text that failed to decode: {response.text}")
            return None

    except requests.exceptions.HTTPError as http_err:
        # Log additional details for the HTTP error
        print(f"HTTP error occurred: {http_err}")
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        return None
    except Exception as err:
        # Catch-all for any other exceptions and log them
        print(f"An error occurred: {err}")
        return None





async def calculate_day_performance(message_ids_dict, start_balance_str, end_balance_str, channel):
    trades_str_list = []
    BP_float_list = []
    for message_id in message_ids_dict.values():
        message = await channel.fetch_message(message_id)
        if message:
            trade_info_dict = extract_trade_results(message.content, message_id)
            if isinstance(trade_info_dict, str) and "Invalid" in trade_info_dict:
                continue
            
            trade_info_str = f"${trade_info_dict['total']:.2f}, {trade_info_dict['percent']:.2f}%{trade_info_dict['profit_indicator']}"
            trades_str_list.append(trade_info_str)
            BP_float_list.append(trade_info_dict['total_investment'])

    total_bp_used_today = sum(BP_float_list)
    trades_str = '\n'.join(trades_str_list)
    start_balance = float(start_balance_str.replace("$", "").replace(",", ""))
    end_balance = float(end_balance_str.replace("$", "").replace(",", ""))
    profit_loss = end_balance - start_balance
    percent_gl = (profit_loss / start_balance) * 100

    output_msg = f"""
All Trades:
{trades_str}

Total BP Used Today:
${total_bp_used_today:,.2f}

Account balance:
Start: {start_balance_str}
End: {end_balance_str}

Profit/Loss: ${profit_loss:,.2f}
Percent Gain/Loss: {percent_gl:.2f}%
"""
    return output_msg

def extract_trade_results(message, message_id):
    clean_message = ''.join(e for e in message if (e.isalnum() or e.isspace() or e in ['$', '.', ':', '-']))
    investment_pattern = r"Total Investment: \$(.+)"
    investment_match = re.search(investment_pattern, clean_message)
    total_investment = float(investment_match.group(1).replace(",", "")) if investment_match else 0.0

    results_pattern = r"AVG BID:.*?(-?\d{1,3}(?:,\d{3})*\.\d{2}).*?TOTAL:.*?(-?\d{1,3}(?:,\d{3})*\.\d{2})(✅|❌).*?PERCENT:.*?(-?\d+\.\d+)%"
    results_match = re.search(results_pattern, message, re.DOTALL)
    if results_match:
        avg_bid = float(results_match.group(1))
        total = float(results_match.group(2))
        profit_indicator = results_match.group(3)
        percent = float(results_match.group(4))
        
        return {
            "avg_bid": avg_bid,
            "total": total,
            "profit_indicator": profit_indicator,
            "percent": percent,
            "total_investment": total_investment
        }
    else:
        return f"Invalid Results Details for message ID {message_id}"














async def market_hours_check():
    market_open_printed = False
    
    while True:
        now = datetime.now(pytz.timezone("US/Eastern"))
        #Market Closed
        if now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.hour >= 16:
            refresh_buttons.stop()
            print("refresh_buttons Stopped")
            market_open_printed = False
            # Calculate time until market open
            market_open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
            if now.hour >= 16:
                market_open_time += timedelta(days=1)
            time_until_open = market_open_time - now
            hours, remainder = divmod(time_until_open.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"Market is closed. Waiting {hours:02}:{minutes:02}:{seconds:02} until the market opens.")

            #GET/PRINT ACCOUNT BALANCE AT END OF DAY
            account_balance = await get_account_balance(real_money_activated)
            if account_balance:
                formatted_balance = "${:,.2f}".format(account_balance)
                await print_discord(f"\nMarket is closed. Today's closing balance: {formatted_balance}")
                #calculations here
                channel = bot.get_channel(cred.DISCORD_CHANNEL_ID)

                #change these 2 values incase of any errors today, need a reset of program
                #message_ids_dict = {'AAPL-call-185.00-20231110-20231108090756256367': 1171828470293200906, 'QQQ-put-371.00-20231108-20231108091804793307': 1171831022367801404, 'TSLA-put-210.00-20231110-20231108093636538432': 1171835686492573757, 'QQQ-put-371.00-20231108-20231108111620703358': 1171860786998673550, 'IWM-put-170.00-20231108-20231108111642530952': 1171860877826334760}
                #Today_Start_Balance = "$18,229.47"

                Today_End_Balance = formatted_balance
                output_message = await calculate_day_performance(message_ids_dict, Today_Start_Balance, Today_End_Balance, channel)
                await print_discord(output_message)
                message_ids_dict.clear()

            await asyncio.sleep(time_until_open.total_seconds())
        #Market Open
        else:
            if not market_open_printed:
                refresh_buttons.start()
                account_balance = await get_account_balance(real_money_activated)
                if account_balance:
                    formatted_balance = "${:,.2f}".format(account_balance)
                    await print_discord(f"\nMarket is OPEN! Ready BP Today: {formatted_balance}")
                    market_open_printed = True
                    #calculations here
                    Today_Start_Balance = formatted_balance
                    Today_End_Balance = ""

            await asyncio.sleep(5)
        












async def sell_button_generation(ticker_symbol, num_contracts, cp, strike_price, expiration_date, timestamp):
    global total_sold_percentage
    total_sold_percentage = 0

    # Generate buttons
    buttons = generate_buttons(num_contracts)
    
    # Create a message with buttons
    message = f"Bought {num_contracts} {ticker_symbol} ({cp}): {buttons}"
    message2= f"Bought {num_contracts} {ticker_symbol} ({cp})"

    # Create button data
    button_data = []
    for percentage in buttons:
        num_contracts_to_sell = int(num_contracts * (percentage / 100))
        button_id = f"{ticker_symbol}_{num_contracts_to_sell}_{percentage}_{cp}_{strike_price}_{timestamp}"  # Unique identifier for each button
        button_data.append({"style": discord.ButtonStyle.primary, "label": f"Sell {percentage}%", "custom_id": button_id})
        #button_data.append({"style": discord.ButtonStyle.primary, "label": f"{button_id}", "custom_id": button_id})
        # Store contract information in the dictionary
        contract_info = {
            "ticker_symbol": ticker_symbol,
            "percentage": percentage,
            "cp": cp, #call or put
            "strike_price": strike_price,
            "expiration_date": expiration_date
        }
        button_contract_info[button_id] = contract_info
        #print(f"\nbutton_contract_info: {button_contract_info}\n")
        
    # send message
    await print_discord(message, message2, button_data=button_data, delete_last_message=True)

class StopScriptException(Exception):
    pass

async def Stop_script(msg_str, str_stopException):
    await print_discord(msg_str)
    await bot.close()
    raise StopScriptException(str_stopException)

@bot.event
async def on_ready():
    global message_with_buttons
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

                    if quantity == "not specified":  # default amount of contracts
                        #TODO: MATH of quantity
                        quantity = calculate_quantity(),,,

                    last_trade_info['ticker_symbol'] = ticker_symbol
                    last_trade_info['strike'] = strike
                    last_trade_info['cp'] = cp
                    last_trade_info['expiration_date'] = expiration_date
                    last_trade_info['quantity'] = quantity

                    print(f"expiration_date: {expiration_date}\n")

                    
                    order_result = await submit_option_order(ticker_symbol, strike, cp, bid, expiration_date, quantity, side, order_type)
                    if order_result:
                        timestamp = generate_timestamp()
                        await get_order_status(order_result['order_id'], "buy", ticker_symbol, cp, strike, expiration_date, timestamp)
                
        elif action == "do_nothing":
            await print_discord("Action: doing nothing, waiting for new message")
    await bot.process_commands(message)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    print("\nButton Clicked-----------------------------------------------------------")
    global message_with_buttons  # Declare the variable as global
    # Defer the interaction, indicating that we plan to edit the original message.
    await interaction.response.defer()
    global total_sold_percentage
    global button_contract_info
    print(f"total_sold_percentage: {total_sold_percentage}")
    if interaction.is_component:
        custom_btn_id = interaction.custom_id
        print(f"Custom ID: {custom_btn_id}")

        # Extract the number of contracts to sell directly from custom_id
        ticker_symbol, num_of_contracts_to_sell, _, cp, strike_price, timestamp_from_button = custom_btn_id.split('_')
        num_of_contracts_to_sell = int(num_of_contracts_to_sell)

        contract_info = button_contract_info.get(custom_btn_id)
        print(f"Contract Info: {contract_info}")

        if contract_info:
            #selling logic here
            bid = None
            side = "sell_to_close"
            order_type = "market"

            order_result = await submit_option_order(ticker_symbol, strike_price, cp, bid, contract_info["expiration_date"], num_of_contracts_to_sell, side, order_type)
            
            if order_result:
                total_sold_percentage += contract_info["percentage"]
                print(f"Updated Total Sold Percentage: {total_sold_percentage}%")
                await get_order_status(order_result['order_id'], "sell", contract_info["ticker_symbol"], contract_info["cp"], strike_price, contract_info["expiration_date"], timestamp_from_button)
                
                # Defer the interaction, indicating that we plan to edit the original message.
                #await interaction.response.defer()
                updated_view = create_updated_view(total_sold_percentage)

                if message_with_buttons:  # make sure it's not None
                    await message_with_buttons.edit(view=updated_view)

                # Check if all contracts are sold, if so, clear the view
                if total_sold_percentage >= 100:
                    print("All contracts sold. Clearing the view.")
                    button_contract_info.clear()
                    await interaction.message.edit(content=interaction.message.content, view=None)
                    #GET LAST MESSAGE BOT SENT AND ADD THIS TO THE END OF THERE MESSAGE: ($XX, +-XX.XX%✅❌)
                    message_channel = interaction.channel
                    unique_order_key = generate_unique_key(ticker_symbol, cp, strike_price, contract_info["expiration_date"], timestamp_from_button)
                    message_context = await message_channel.fetch_message(message_ids_dict[unique_order_key])
                    
                    # Assuming all orders related to that unique_order_key are closed if you reach this point
                    # Calculate trade details
                    if isinstance(message_context, discord.Message):
                        trade_info = calculate_profit_percentage(message_context.content)
                    else:
                        print("message_context is not a Discord message object.")

                    # Append the trade info to the user's message and edit it
                    new_user_msg_content = message_context.content + trade_info

                    await message_context.edit(content=new_user_msg_content) 
                else:
                    await interaction.message.edit(content=interaction.message.content, view=updated_view)
            else:
                print("Order submission failed, not updating total_sold_percentage or view.")
                await interaction.response.send_message("Order submission failed.", ephemeral=True)
        else:
            print("Contract info not found")
            await interaction.response.send_message("Contract information not found.", ephemeral=True)

# Function to create updated view
def create_updated_view(sold_percentage: int):
    global total_sold_percentage
    remaining_percentage = 100 - sold_percentage
    print(f"Remaining Percentage: {remaining_percentage}%")
    # Extract button data from the current button_contract_info
    current_button_data = []
    for btn_id, contract_info in button_contract_info.items():

        current_button_data.append({
            "style": discord.ButtonStyle.primary,
            "label": f"Sell {contract_info['percentage']}%",
            "custom_id": btn_id
        })

    #print(f"\nCurrent_button_data: {current_button_data}\n")
    view = MyView(current_button_data)  # initialize the MyView with button_data

    # Adjust the buttons' disabled states based on the total sold percentage
    for btn in view.children:
        contract_info = button_contract_info[btn.custom_id]
        remaining_after_this_sell = remaining_percentage - contract_info["percentage"]
        btn.disabled = remaining_after_this_sell < 0

        # Printing out information about each button and its state
        #print(f"Button {btn.custom_id} - Percentage: {contract_info['percentage']}% - Remaining after this sell: {remaining_after_this_sell}% - Disabled: {btn.disabled}") # Add this

    return view

@tasks.loop(minutes=14)  # adjust the time as needed
async def refresh_buttons():
    print("Start button refresh")
    global message_with_buttons
    try:
        # Use your existing state tracking to generate new button data
        new_button_data = []
        for btn_id, contract_info in button_contract_info.items():
            new_button_data.append({
                "style": discord.ButtonStyle.primary,
                "label": f"Sell {contract_info['percentage']}%",
                "custom_id": btn_id
            })

        # Create a new view using the updated button data
        new_view = MyView(new_button_data)

        # Edit the message with the new view
        if message_with_buttons:  # check if it's not None or uninitialized
            await message_with_buttons.edit(view=new_view)  # Using `edit` method of Message object to update its view
    except Exception as e:
        print(f"An error occurred while refreshing buttons: {e}")

if __name__ == "__main__":

    async def run_bot():
        while True:
            try:
                await bot.start(cred.DISCORD_TOKEN)
            except Exception as e:
                await print_discord(f"Exception occurred: {e}")
                await asyncio.sleep(60)  # Pause for a minute before restarting the bot

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_bot())