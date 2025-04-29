import asyncio
import random
from telethon import TelegramClient
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction

# Your Telegram API credentials
API_ID = 27684248  
API_HASH = 'dfad47a46d4429b2408a51084bc4fc71'
PHONE = '+998336157489'

# Initialize client
client = TelegramClient('session_main', API_ID, API_HASH)

# Target chat (can be 'me' for yourself or a username like '@example')
TARGET = '@manxorazmiyim'  # or '@manxorazmiyim'

# List of random messages
MESSAGES = [
    "Hello 👋",
    "What's up?",
    "How are you?",
    "Just checking in!",
    "😊",
    "Busy day!",
    "Hope you're doing well!",
]

async def stay_online():
    await client.start(phone=PHONE)
    print("✅ Logged in successfully!")

    while True:
        try:
            action = random.choice(["typing", "message"])
            
            if action == "typing":
                # Simulate typing action
                await client(SetTypingRequest(
                    peer=TARGET,
                    action=SendMessageTypingAction()
                ))
                print("📝 Sent typing action...")
                await asyncio.sleep(random.randint(10, 25))  # typing for 10-25 sec
                
            else:
                # Send real message
                message = random.choice(MESSAGES)
                await client.send_message(TARGET, message)
                print(f"✉️ Sent message: {message}")
                await asyncio.sleep(random.randint(40, 90))  # rest after message

        except Exception as e:
            print(f"❗ Error: {e}")
            await asyncio.sleep(random.randint(20, 40))  # small wait on error

async def main():
    await stay_online()

if __name__ == '__main__':
    asyncio.run(main())
