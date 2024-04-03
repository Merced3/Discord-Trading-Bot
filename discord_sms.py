#this file is currently not being used, might use it latter... who knows.


import cred
from twilio.rest import Client
import asyncio
from discord import Intents
import discord
from discord.ext import commands

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

bot = commands.Bot(command_prefix='!', intents=intents)
twilio_client = Client(cred.TWILIO_ACCOUNT_SID, cred.TWILIO_AUTH_TOKEN)
phone_numbers = [cred.Z_PHONE_NUMBER, cred.CED_PHONE_NUMBER]

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}\n")

@bot.event
async def on_message(message):
    if message.channel.id == cred.DISCORD_CHANNEL_ID:
        print(f"{message.content}")
        if message.author == bot.user:
            return

        if message.content:
            for number in phone_numbers:
                twilio_client.messages.create(
                    body=(f"Testing server: {message.content}"),
                    from_=cred.TWILIO_PHONE_NUMBER,
                    to=number
                )

        await bot.process_commands(message)



if __name__ == "__main__":
    bot.run(cred.DISCORD_TOKEN)
