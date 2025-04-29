import asyncpg
import asyncio
from telethon import TelegramClient, events

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
    "@lorry_xalqaro_yuk_guruhlar",
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
                message_text TEXT NOT NULL, 
                channel_name TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (sender_id, message_text)  -- Avoid duplicate messages
            )
        """)

async def message_exists(pool, sender_id, text):
    """Check if a message with the same sender_id and text exists in the database."""
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT 1 FROM telegram_messages WHERE sender_id = $1 AND message_text = $2",
            sender_id, text
        )
    return result is not None

async def save_to_db(pool, sender_id, text, channel):
    """Save messages to PostgreSQL only if they don't already exist."""
    if not await message_exists(pool, sender_id, text):  # Avoid duplicates
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO telegram_messages (sender_id, message_text, channel_name)
                VALUES ($1, $2, $3)
                """,
                sender_id, text, channel
            )
        print(f"Saved to DB: [{channel}] {sender_id}: {text}")
    else:
        print(f"Duplicate skipped: [{channel}] {sender_id}: {text}")

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
        await save_to_db(pool, sender_id, text, channel)

    await client.start(PHONE_NUMBER)

    # Fetch last 10 messages for each channel and save them if not duplicates
    for channel in CHANNELS:
        async for message in client.iter_messages(channel, limit=10):
            if message.text:
                await save_to_db(pool, message.sender_id, message.text, channel)

    print("Listening for new messages...")
    await client.run_until_disconnected()
    await pool.close()

asyncio.run(main())