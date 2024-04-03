import asyncio
import requests
import multiprocessing
from multiprocessing import Queue
from datetime import datetime, timedelta
import pytz
import discord
from discord import Intents
import cred
from twilio.rest import Client
import text_classification
from buy_classification import extract_info_from_message
from sell_classification import classify_sell_message



class TradeManager:
    def __init__(self):
        self.paper_trading = True
        self.real_money = False

        self.paper_trading_contract_quantity = 10
        self.real_money_contract_quantity = 1

        self.discord_channel_id = cred.DISCORD_CHANNEL_ID
        self.trade_queue = Queue()

    async def send_sms(self, body_message):
        # Send total profits using Twilio
        account_sid = cred.TWILIO_ACCOUNT_SID
        auth_token = cred.TWILIO_AUTH_TOKEN

        async def _send_sms():
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body=body_message,
                from_=cred.TWILIO_PHONE_NUMBER,
                to=cred.MY_PHONE_NUMBER
            )
            return message.sid

        message_sid = await asyncio.to_thread(_send_sms)
        return message_sid

    async def print_sms(self, message1, message2=None, message=None):

        # Now that send_sms is defined, you can call it.
        if message2:
            print(message1)
            if message:
                await message.channel.send(message2) 
            await self.send_sms(message2)
        else:
            print(message)
            if message:
                await message.channel.send(message1)
            await self.send_sms(message1)


        


    def get_endpoint_and_headers(self):
        if self.real_money and not self.paper_trading:
            return (
                f"{cred.TRADIER_BROKERAGE_BASE_URL}accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/orders",
                {
                    "Authorization": f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",
                    "Accept": "application/json"
                }
            )
        elif self.paper_trading and not self.real_money:
            return (
                f"{cred.TRADIER_SANDBOX_BASE_URL}accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/orders",
                {
                    "Authorization": f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}",
                    "Accept": "application/json"
                }
            )
        else:
            raise ValueError("Cannot work with Both paper_trading and real_money being 'True' or 'False' at the same time.")

    async def submit_option_order(self, symbol, strike, option_type, bid, expiration_date, quantity, side, order_type):
        
        order_url, headers = self.get_endpoint_and_headers()

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
                await self.print_sms("Order Submitted", f"{symbol} Order Pending")
                result = {'order_id': response_data['order']['id']}
                if bid and bid != 'not specified':
                    result['total_value'] = float(bid) * quantity * 100
                return result
            elif 'error' in response_data['errors']:
                #getting account balance
                if self.real_money and not self.paper_trading:
                    endpoint = f'https://api.tradier.com/v1/accounts/{cred.TRADIER_BROKERAGE_ACCOUNT_NUMBER}/balances'
                    headers = {'Authorization': f"Bearer {cred.TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN}",'Accept': 'application/json'}
                elif self.paper_trading and not self.real_money:
                    endpoint = f'https://api.tradier.com/v1/accounts/{cred.TRADIER_SANDBOX_ACCOUNT_NUMBER}/balances'
                    headers = {'Authorization': f"Bearer {cred.TRADIER_SANDBOX_ACCESS_TOKEN}",'Accept': 'application/json'}
                response = requests.get(endpoint,headers=headers)
                json_response = response.json()
                
                if 'cash' in json_response['balances']:
                    account_buying_power = json_response['balances']['cash']['cash_available']
                    order_cost = float(bid) * quantity * 100 if bid and bid != 'not specified' else 0
                    await self.print_sms(f"\nOrder submission failed. Settled Funds too low: ${account_buying_power}. Order Cost: ${order_cost}")
                else:
                    await self.print_sms(f"\nOrder submission failed. Settled Funds not available. Account Response content: {response.content}")
            else:
                await self.print_sms(f"\nOrder submission failed. Response content: {response.content}")
        else:
            await self.print_sms(f"\nOrder submission failed. Response status code: {response.status_code}", f"Order failed, response content: {response.content}")
            return None



    
    def add_trade_task(self, action, ticker_symbol, strike, cp, bid, expiration_date, quantity):
        print("Entering add_trade_task function...")
        print(f"Task Created: {ticker_symbol}")
        self.trade_queue.put((action, ticker_symbol, strike, cp, bid, expiration_date, quantity))
        print("Task added to trade_queue")

    async def start_trade_handling(self):
        print("Starting trade handling process...")
        try:
            await self.trade_handler()  # Running it in the main process for testing
        except Exception as e:
            print(f"Error in start_trade_handling: {e}")
        process = multiprocessing.Process(target=self.trade_handler)
        process.start()
        print("Trade handling process started")

    async def trade_handler(self):
        print("Entered trade_handler")
        try:
            while True:
                queue_size = self.trade_queue.qsize()
                print(f"Current trade queue size: {queue_size}")

                if not self.trade_queue.empty():
                    print("Trade queue not empty, processing trade...")
                    action, ticker_symbol, strike, cp, bid, expiration_date, quantity = self.trade_queue.get()
                    
                    print(f"Processing trade for {ticker_symbol}")
                    
                    # Depending on your setup, you might want to derive side and order_type here
                    side = 'buy' if action == "buy" else 'sell'
                    order_type = 'market' if bid is None or bid == 'not specified' else 'limit'

                    if action == "buy":
                        print("Placing buy")
                        # For buying, we'll use the submit_option_order function
                        await self.submit_option_order(
                            symbol=ticker_symbol,
                            strike=strike,
                            option_type=cp,  # Assuming cp means call or put
                            bid=bid,
                            expiration_date=expiration_date,
                            quantity=quantity,
                            side=side,
                            order_type=order_type
                        )
                        print(f"Buy order for {ticker_symbol} placed")

                    elif action == "sell":
                        print("Placing sell")
                        # For selling, use the submit_option_order function too but ensure the side is set to 'sell'
                        await self.submit_option_order(
                            symbol=ticker_symbol,
                            strike=strike,
                            option_type=cp,  # Assuming cp means call or put
                            bid=bid,
                            expiration_date=expiration_date,
                            quantity=quantity,
                            side=side,
                            order_type=order_type
                        )
                        print(f"Sell order for {ticker_symbol} placed")

                else:
                    print("Trade queue is empty, sleeping for 5 seconds...")

                # Sleep to avoid excessive CPU usage
                await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in trade_handler: {e}")

    def predict_action(self, message_content):
        action = text_classification.predict_action(text_classification.clf, text_classification.vectorizer, message_content)
        print(f"Predicting most likely action: {action}\n")
        return action
    
    def classify_sell_message(self, message):
        return classify_sell_message(message)
    
    def extract_info_from_message(self, message):
        return extract_info_from_message(message)