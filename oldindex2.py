import json
import asyncpg
import asyncio
import openai
from telethon import TelegramClient, events
import os
from dotenv import load_dotenv

# OpenAI API Key
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Telegram API Credentials
API_ID = 27684248  
API_HASH = "dfad47a46d4429b2408a51084bc4fc71"
PHONE_NUMBER = "+998336157489"

# List of channels to listen to
CHANNELS = [
    "@yuk_markazi_gruppaaaa",
    "@lorry_xalqaro_yukla",
    "@lorry_yuk_markazi",
    "@fargona_toshkent_samarqand_yuk",
    "@Yuk_markazi_yuk_yukla",
    "@jizzaxyukmarkazi25",
    "@lorry_xalqaro_yuk_guruhlar"
]

# PostgreSQL Config
DB_CONFIG = {
    "user": "postgres",
    "password": "postgres",
    "database": "postgres",
    "host": "localhost",
    "port": 5432
}

async def create_table(pool):
    """Ensure the table exists before inserting data."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id SERIAL PRIMARY KEY,
                sender_id BIGINT NOT NULL,
                message_json JSONB NOT NULL,
                channel_name TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (sender_id, message_json)  -- Avoid duplicate messages
            )
        """)

async def message_exists(pool, sender_id, message_json):
    """Check if a message with the same sender_id and structured JSON exists in the database."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT 1 FROM telegram_messages WHERE sender_id = $1 AND message_json::text = $2",
            sender_id, json.dumps(message_json, ensure_ascii=False)
        )
    return result is not None

async def save_to_db(pool, sender_id, message_json, channel):
    """Save structured messages to PostgreSQL only if they don't already exist."""
    if not await message_exists(pool, sender_id, message_json):
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO telegram_messages (sender_id, message_json, channel_name)
                VALUES ($1, $2, $3)
                """,
                sender_id, json.dumps(message_json, ensure_ascii=False), channel
            )
        print(f"Saved to DB: [{channel}] {sender_id}: {message_json}")
    else:
        print(f"Duplicate skipped: [{channel}] {sender_id}: {message_json}")


def convert_text_to_json(text: str) -> dict:
    """
    Converts the given text into a structured JSON object.
    - Removes icons, emojis, and extra symbols.
    - Ensures Uzbek phone numbers start with "998".
    - Extracts and formats relevant data.
    """
    prompt = f"""
    Convert the following text into a JSON object with the keys: fromA, fromB, phone, comment, and vehicle.
    - Remove icons, emojis, and extra symbols.
    - Ensure phone numbers follow the Uzbek format (if they don’t start with 998, prepend it).
    - Extract relevant text while keeping the structure clean.
    
    Text:  
    {text}
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    generated_json = json.loads(response.choices[0].message.content)
    
    if "phone" in generated_json and not generated_json["phone"].startswith("998"):
        generated_json["phone"] = "998" + generated_json["phone"]
    
    return generated_json

async def main():
    """Use a single client to listen to multiple channels."""
    pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=5)
    await create_table(pool)
    
    client = TelegramClient("session_main", API_ID, API_HASH)

    @client.on(events.NewMessage(chats=CHANNELS))
    async def handler(event):
        sender_id = event.message.sender_id
        text = event.message.text
        channel = event.chat.title
        message_json = convert_text_to_json(text)
        await save_to_db(pool, sender_id, message_json, channel)

    await client.start(PHONE_NUMBER)
    
    # Fetch last 10 messages for each channel and save them if not duplicates
    for channel in CHANNELS:
        async for message in client.iter_messages(channel, limit=10):
            if message.text:
                message_json = convert_text_to_json(message.text)
                await save_to_db(pool, message.sender_id, message_json, channel)
    
    print("Listening for new messages...")
    await client.run_until_disconnected()
    await pool.close()

asyncio.run(main())
