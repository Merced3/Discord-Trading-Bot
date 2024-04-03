import unittest
import asyncio
import main

class TestCheckStopMessage(unittest.TestCase):
    
    async def test_check_stop_message(self):
        # Test if the function returns False when no "Stop trading" message is received
        stop_received = await main.check_stop_message()
        self.assertFalse(stop_received)

        # Test if the function returns True when a "Stop trading" message is received
        # You can send a message to your Twilio number with the body "Stop trading" to test this
        # Make sure the message is sent during market hours, otherwise the script will exit with a "Market Hours Ended" message
        stop_received = await main.check_stop_message()
        self.assertTrue(stop_received)

if __name__ == '__main__':
    asyncio.run(TestCheckStopMessage().test_check_stop_message())
