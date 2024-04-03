To set up and run the Discord bot, follow these steps:

1. Create a bot in the Discord Developer Portal:
   a. Go to the Discord Developer Portal: https://discord.com/developers/applications
   b. Click "New Application" and enter a name for your application.
   c. Navigate to the "Bot" tab and click "Add Bot".
   d. Copy the bot token; you'll need it for your code.

2. Set up the bot's intents:
   a. In the "Bot" tab, scroll down to the "Privileged Gateway Intents" section.
   b. Enable the "Server Members Intent" toggle.
   c. Enable the "Message Content Intent" toggle.
   d. Save your changes.

3. Invite the bot to your server:
   a. Go to the "OAuth2" tab in the developer portal.
   b. In the "Scopes" section, select the "bot" checkbox.
   c. In the "Bot Permissions" section, select the required permissions for your bot.
   d. Copy the generated invite link and open it in your browser.
   e. Choose the server to add your bot to and authorize the bot.

4. Set up the Python environment:
   a. Install Python3 venv folder:
      - 'python3 -m venv venv'
   b. Activate venv folder:
      - Windows: 'venv\Scripts\activate'
      - Unix-based systems: 'source venv/bin/activate'
   b. Install requirements.txt folder
      - 'pip install -r requirements.txt'

5. Set up your Tradier brokerage account:
   a. Create a Tradier brokerage account: https://brokerage.tradier.com/
   b. To access the Tradier API, sign up for a developer account: https://developer.tradier.com/
   c. Create a new application to obtain your API access token.
   d. For paper trading, enable the "Sandbox" option in your Tradier developer account.

6. Update the cred.py file with the necessary credentials:
   a. Discord API credentials:
      - DISCORD_TOKEN: Your bot's token from the Discord Developer Portal.
      - DISCORD_CHANNEL_ID: The ID of the channel where the bot should listen for messages.
      - DISCORD_APPLICATION_ID: The application ID from the Discord Developer Portal.
      - DISCORD_PUBLIC_KEY: The public key from the Discord Developer Portal.
   b. Tradier API credentials:
      - TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN: Your Tradier brokerage account access token for real-money trading.
      - TRADIER_BROKERAGE_BASE_URL: The base URL for the Tradier brokerage API for real-money trading (https://api.tradier.com/v1/).
      - TRADIER_BROKERAGE_STREAMING_URL: The streaming URL for the Tradier brokerage API for real-money trading (https://stream.tradier.com/v1/).
      - TRADIER_SANDBOX_ACCOUNT_NUMBER: Your Tradier sandbox account number for paper trading.
      - TRADIER_SANDBOX_ACCESS_TOKEN: Your Tradier sandbox access token for paper trading.
      - TRADIER_SANDBOX_BASE_URL: The base URL for the Tradier sandbox API for paper trading (https://sandbox.tradier.com/v1/).

   P.S. Please ensure that you provide the correct information for each credential, and remember to keep your credentials secure. Do not share them with anyone.

7. Run the bot:
   a. Open a terminal or command prompt.
   b. Navigate to the directory containing your main_interactive.py script.
   c. Run the script: 'python main_interactive.py'

Extra info about tradier:
   - tradier brokerage review: https://www.stockbrokers.com/review/tradier