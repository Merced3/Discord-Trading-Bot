import asyncio
from main_interactive import get_account_balance

async def main():
    ab_money = await get_account_balance(True)

    print(f"\nAccount Balance: ${ab_money}")

if __name__ == "__main__":
    asyncio.run(main())