import discord
from discord import Intents
from discord.ext import commands
import asyncio
import multiprocessing
from trade_manager import TradeManager
import cred
from datetime import datetime, timedelta
import pytz

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize the trade manager
trade_manager = TradeManager()

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}\n")
    if trade_manager.paper_trading and not trade_manager.real_money:
        await trade_manager.print_sms("Paper Trading Activated\n")
    elif trade_manager.real_money and not trade_manager.paper_trading:
        await trade_manager.print_sms("Real Money Activated\n")
    else:
        await trade_manager.print_sms("Change variable values (real_money, paper_trading) because the script cannot run correctly with them both being the same value\n")
    
    await trade_manager.start_trade_handling()
    bot.loop.create_task(market_hours_check())

@bot.event
async def on_message(message):
    if message.channel.id == trade_manager.discord_channel_id:
        print("__________________________________________________________________________________________________________________________________________")
        print(f"Received message from 🚨-trades: {message.content}")

        action = trade_manager.predict_action(message.content)
        print(f"Predicting most likely action: {action}\n")

        if action == "buy":
            info = trade_manager.extract_info_from_message(message.content)
            print(f"Info returned: {info}")
            cp, bid, expiration_date, quantity, strike, ticker_symbol = info

            if ticker_symbol == "not specified" or strike == "not specified" or cp == "not specified":
                await trade_manager.print_sms("Canceled the buy, not enough information was disclosed", message=message)
            else:
                trade_manager.add_trade_task(action="buy", ticker_symbol=ticker_symbol, strike=strike, cp=cp, bid=bid, expiration_date=expiration_date, quantity=quantity)
                
        elif action == "sell":
            sell_percentage = trade_manager.classify_sell_message(message.content)
            print(f"Predicted sell percentage: {sell_percentage} for message: {message.content}")
            # Implement sell logic here and add sell trade tasks to the trade manager.

        elif action == "do_nothing":
            await trade_manager.print_sms("Action: doing nothing, waiting for a new message", "Action: doing nothing", message=message)

    await bot.process_commands(message)

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
                print("Market is OPEN!")
                market_open_printed = True
            await asyncio.sleep(5)

if __name__ == "__main__":
    trade_manager.start_trade_handling()
    bot.run(cred.DISCORD_TOKEN)
