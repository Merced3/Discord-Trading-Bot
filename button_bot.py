import discord
from discord.ext import commands
from discord.ui import View, Button
import cred  # Importing your cred module

intents = discord.Intents.all()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


class MyView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Click Me!", style=discord.ButtonStyle.primary)
    async def click_button(self, button: Button, interaction: discord.Interaction):
        # Reply directly to the interaction
        await interaction.response.send_message("button clicked")
    
        # Deactivate the button
        button.disabled = True

        # Update the message to show the deactivated button
        await interaction.message.edit(view=self)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    channel = bot.get_channel(cred.DISCORD_CHANNEL_ID)
    await channel.send("Bot is now online!")

@bot.command()
async def send_button(ctx):
    await ctx.send("Here's a button:", view=MyView())

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f'An error occurred: {error}')

bot.run(cred.DISCORD_TOKEN)  # Using the DISCORD_TOKEN from your cred module
