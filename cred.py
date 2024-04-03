#this needs to hold these peices of info for different modes:

# Discord bot related code
DISCORD_TOKEN = ""
DISCORD_CHANNEL_ID = 0
DISCORD_APPLICATION_ID = 0
DISCORD_PUBLIC_KEY = ""

#twilio info
TWILIO_ACCOUNT_SID = ''
TWILIO_AUTH_TOKEN = ''
TWILIO_PHONE_NUMBER = '+12345678910'
MY_PHONE_NUMBER = '+12345678910'

# Options trading-related code
TRADIER_BROKERAGE_ACCOUNT_ACCESS_TOKEN = "" #Real money
TRADIER_BROKERAGE_BASE_URL = "https://api.tradier.com/v1/"              #Real money (Request/Response)
TRADIER_BROKERAGE_STREAMING_URL = "https://stream.tradier.com/v1/"      #Real money (Streaming)
TRADIER_BROKERAGE_ACCOUNT_NUMBER = ""
#account number does not exist for the brokerage account

TRADIER_SANDBOX_ACCOUNT_NUMBER = ""                           #Paper trading
TRADIER_SANDBOX_ACCESS_TOKEN = ""           #Paper trading
TRADIER_SANDBOX_BASE_URL = "https://sandbox.tradier.com/v1/"            #Paper trading (Request/Response)
#streaming for sandbox API not available