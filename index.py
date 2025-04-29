import os
import json
import asyncpg
import asyncio
import openai
import json
import requests
import time
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Load API keys from environment variables
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


API_ID = 27684248  
API_HASH = "dfad47a46d4429b2408a51084bc4fc71"
PHONE_NUMBER = "+998336157489"

# Telegram Channels
CHANNELS = [
    "@lorry_yuk_markazi",
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
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id SERIAL PRIMARY KEY,
                sender_id BIGINT NOT NULL,
                message_text TEXT NOT NULL,
                message_json JSONB NOT NULL,
                channel_name TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (sender_id, message_text)
            )
        """)

async def message_exists_text(pool, sender_id, message_text):
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            """
            SELECT 1
            FROM telegram_messages
            WHERE sender_id = $1
              AND message_text = $2
              AND received_at >= NOW() - INTERVAL '24 HOURS'
            """,
            sender_id, message_text
        )
    return result is not None

# async def save_to_db(pool, sender_id, message_text, message_json, channel):
#     async with pool.acquire() as conn:
#         await conn.execute(
#             """
#             INSERT INTO telegram_messages (sender_id, message_text, message_json, channel_name)
#             VALUES ($1, $2, $3, $4)
#             """,
#             sender_id, message_text, json.dumps(message_json, ensure_ascii=False), channel
#         )
#     # print(f"✅ Saved to DB: [{channel}] {sender_id}")


async def save_to_db(pool, sender_id, message_text, message_json, channel):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO telegram_messages (sender_id, message_text, message_json, channel_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (sender_id, message_text)
            DO UPDATE SET
                message_json = EXCLUDED.message_json,
                channel_name = EXCLUDED.channel_name,
                received_at = NOW()
            """,
            sender_id, message_text, json.dumps(message_json, ensure_ascii=False), channel
        )
    # # print(f"✅ Saved/Updated to DB: [{channel}] {sender_id}")

def transform_json(input_json, comment: str):
    if isinstance(input_json, list):  # If input is a list of objects
        return [transform_json(item, comment) for item in input_json]
    
    if (input_json.get("phone", "") == "" or input_json.get("phone", "") == "998" or input_json.get("phone", "") == None): 
        return {}
    

    return {
        "destinationARegion": input_json.get("fromARegion", ""),
        "destinationADistinct": input_json.get("fromADistrict", ""),
        "destinationBRegion": input_json.get("toBRegion", ""),
        "destinationBDistinct": input_json.get("toBDistrict", ""),
        "transportType": input_json.get("transport", ""),
        "comment": comment,
        "phone": input_json.get("phone", "")
    }

def send_request(json_data, comment: str):
    url = "https://api.e-yuk.uz//cargo/create"  # Replace with actual API URL
    headers = {"Content-Type": "application/json"}

    if isinstance(json_data, list):
        for item in json_data:
            response = requests.post(url, headers=headers, json=transform_json(item, comment))
            # print(f"📤 Sending: {transform_json(item, comment)}")
            # print(f"📩 Response: {response.status_code}, {response.text}")
    else:
        response = requests.post(url, headers=headers, json=transform_json(json_data, comment))
        # print(f"📤 Sending: {transform_json(json_data, comment)}")
        # print(f"📩 Response: {response.status_code}, {response.text}")

def convert_text_to_json(text: str) -> dict:
    start_time = time.perf_counter()

    if not text.strip():
        return {"error": "Empty message"}

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                 {
                    "role": "system",
                    "content": "Siz faqat quyidagi JSON formatida javob beradigan bot siz:\n{\n  \"fromARegion\": \"Viloyat nomi yoki Davlat nomi\",\n  \"fromADistrict\": \"Tuman/Shahar nomi yoki null\",\n  \"toBRegion\": \"Viloyat nomi yoki Davlat nomi\",\n  \"toBDistrict\": \"Tuman/Shahar nomi yoki null\",\n  \"transport\": \"Transport turi\",\n  \"phone\": \"Telefon raqami\"\n}.\n- Agar joy Oʻzbekistonda boʻlsa, faqat viloyat va shahar/tuman nomlarini aniq ko‘rsat.\n- Agar joy Oʻzbekistondan tashqarida boʻlsa, faqat davlat nomini yoz (masalan, \"Qirgʻiziston respublikasi\" yoki \"Rossiya federatsiyasi\").\n- Har doim aniq JSON formatda qaytar, ortiqcha so‘zlar ishlatma. Telefon raqamni tog'ri kiritilishi men uchun juda ham muhim va bu yerda ortiqcha narsalar hech qachon ishlatilmasligi kerak. {phone: '998917972385'}"
                },
                {"role": "user", "content": text}],
            temperature=0.2
        )

        if not response.choices or not response.choices[0].message.content:
            return None  

        response_text = response.choices[0].message.content.strip()
        
        try:
            comment = text

            generated_json = json.loads(response_text)

            end_time = time.perf_counter()

            elapsed_ms = (end_time - start_time) * 1000  # Convert to milliseconds
            print(f"chatgpt took {elapsed_ms:.2f} ms")
            
            # # print("Comment:", comment)
            send_request(generated_json, comment)
        except json.JSONDecodeError:
            # print(f"⚠️ OpenAI returned invalid JSON:\n{response_text}")
            return None
            
        if "phone" in generated_json and isinstance(generated_json["phone"], str):
            if generated_json["phone"].startswith("+998"):
                generated_json["phone"] = generated_json["phone"][1:]  
            elif not generated_json["phone"].startswith("998"):
                generated_json["phone"] = "998" + generated_json["phone"]

        return generated_json

    except Exception as e:
        # print(f"❌ OpenAI Error: {str(e)}")
        return None

async def main():
    print("🚀 Starting bot...")
    pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=5)
    await create_table(pool)
    
    client = TelegramClient("session_check", API_ID, API_HASH)

    @client.on(events.NewMessage(chats=CHANNELS))
    async def handler(event):
        print("📩 New message received...")
        sender_id = event.message.sender_id
        text = event.message.text or ""
        channel = event.chat.title

        if len(text) < 13:
            print(f"⚠️ Skipped short message from {channel}")
            return

        print(text[:10])

        if not text.strip():
            print(f"⚠️ Skipped empty message from {channel}")
            return

        if any(word in text.lower() for word in ["yopildi", "yopildimi", "reklama", "tarqatmang", "boshqa yuklar:", "aloqaga chiqish"]):
            return

        if await message_exists_text(pool, sender_id, text):
            print(f"⚠️ Duplicate skipped: [{channel}] {sender_id}")
            return

        await save_to_db(pool, sender_id, text, "", channel)

        message_json = convert_text_to_json(text)
        if not message_json:
            print(f"⚠️ Skipped invalid message from {channel}")
            return

        await save_to_db(pool, sender_id, text, message_json, channel)


    await client.start(PHONE_NUMBER)

    for channel in CHANNELS:
        async for message in client.iter_messages(channel, limit=10):
            if not message.text:
                continue  

            sender_id = message.sender_id
            text = message.text

            if await message_exists_text(pool, sender_id, text):
                continue  

            message_json = convert_text_to_json(text)
            if message_json:
                await save_to_db(pool, sender_id, text, message_json, channel)

    # print("✅ Listening for new messages...")
    await client.run_until_disconnected()
    await pool.close()

asyncio.run(main())
