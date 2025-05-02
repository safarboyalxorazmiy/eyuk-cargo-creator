import ahocorasick
import asyncio
import asyncpg
import difflib
import re
import openai
import os
import psycopg2
import json
import time
import requests
import Levenshtein
from psycopg2.extras import RealDictCursor
from typing import Optional
from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

API_ID = 27684248  
API_HASH = "dfad47a46d4429b2408a51084bc4fc71"
PHONE_NUMBER = "+998336157489"

# Telegram Channels
CHANNELS = [
    -1002648857914,
    "@lorry_yuk_markazi"
]

# PostgreSQL Config
DB_CONFIG = {
    "user": "postgres",
    "password": "SardorBugun1taRedBullOldi!#",
    "database": "postgres",
    "host": "localhost",
    "port": 5432
}

def search_by_region(conn, query: str):
    words = query.lower().split()
    found_words = []
    not_found_words = []
    results = []

    sql = """
        SELECT *,
               (CASE WHEN name_uz ILIKE %s THEN 1 ELSE 0 END
              + CASE WHEN name_cy ILIKE %s THEN 1 ELSE 0 END
              + CASE WHEN name_ru ILIKE %s THEN 1 ELSE 0 END) AS score
        FROM regions
        WHERE (name_uz ILIKE %s OR name_cy ILIKE %s OR name_ru ILIKE %s)
        ORDER BY score DESC
        LIMIT 5
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for word in words:
            like_expr = f"%{word}%"
            params = (like_expr, like_expr, like_expr, like_expr, like_expr, like_expr)
            cur.execute(sql, params)
            word_results = cur.fetchall()

            if word_results:
                found_words.append(word)
                results.extend(word_results)
            else:
                not_found_words.append(word)

    return {
        "found_words": found_words,
        "not_found_words": not_found_words,
        "results": results,
    }
    
def search_by_district(conn, query: str):
    def escape_sql(value: str) -> str:
        return value.replace("'", "''")

    def score_eq(field, value, weight):
        value = escape_sql(value)
        return f"{weight} * CASE WHEN LOWER({field}) = '{value}' THEN 1 ELSE 0 END"

    def score_like(field, pattern, weight):
        pattern = escape_sql(pattern)
        return f"{weight} * CASE WHEN LOWER({field}) LIKE '%{pattern}%' THEN 1 ELSE 0 END"

    words = query.lower().split()
    full = query.lower()
    escaped_full = escape_sql(full)

    score_parts = []

    # 🎯 Exact match
    score_parts += [
        score_eq("location_distinct_uz", full, 100),
        score_eq("location_distinct_cy", full, 100),
        score_eq("location_distinct_ru", full, 100),
    ]

    # ✅ Full string LIKE
    score_parts += [
        score_like("location_distinct_uz", full, 20),
        score_like("location_distinct_cy", full, 20),
        score_like("location_distinct_ru", full, 20),
    ]

    # 🧠 Each word LIKE
    for word in words:
        score_parts += [
            score_like("location_distinct_uz", word, 5),
            score_like("location_distinct_cy", word, 5),
            score_like("location_distinct_ru", word, 5),
        ]

    score_sql = " + ".join(score_parts)

    sql = f"""
    SELECT *,
           ({score_sql}) AS match_score
    FROM location
    WHERE ({score_sql}) > 0
    ORDER BY 
        match_score DESC,
        CASE 
            WHEN LOWER(location_distinct_uz) = '{escaped_full}' THEN 1
            WHEN LOWER(location_distinct_cy) = '{escaped_full}' THEN 1
            WHEN LOWER(location_distinct_ru) = '{escaped_full}' THEN 1
            ELSE 2
        END,
        location_distinct_ru
    LIMIT 1
    """

    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql)
        result = cursor.fetchone()
        return result


def load_word_list(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def find_best_match(word: str, wordlist: list, max_distance: int = 5) -> str | None:
    if not word:
        return None

    first_letter = word[0]
    candidates = [w for w in wordlist if w and w[0] == first_letter]

    best_match = None
    best_distance = max_distance + 1

    for candidate in candidates:
        distance = Levenshtein.distance(word, candidate)
        if distance < best_distance:
            best_distance = distance
            best_match = candidate

    if best_distance <= max_distance:
        return best_match
    else:
        return None

def correct_region_names_in_text(text: str, word_list: list, max_distance: int = 5) -> str:
    if "'" in text:
        return text

    corrected_text = text
    candidates = set(re.findall(r"[^\s\d\W\-]+", text, flags=re.UNICODE))

    for word in candidates:
        lower_word = word.lower()
        if lower_word in word_list:
            continue  # Already correct

        best_match = find_best_match(lower_word, word_list, max_distance=max_distance)
        if best_match:
            corrected_text = re.sub(rf"\b{re.escape(word)}\b", best_match, corrected_text)

    return corrected_text


def convert_text_to_json(text: str) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Quyidagi matndan quyidagi JSON formatida ma'lumot chiqar:\n\n"
                        "{\n"
                        '  "from": "...",\n'
                        '  "to": "...",\n'
                        '  "phone": "...",\n'
                        '  "transport": "..."\n'
                        "}\n\n"
                        "from va to o'zgaruvchi qiymatlarida davlat nomlari, shahar, tuman va viloyat qatnashishi mumkin masalan Qozog'iston. Hech qanday ortiqcha emoji, belgilar(🇨🇳 kabi) ishlatilmasligi kerak faqat joylashuv yoki davlat nomini imloviy xatolarsiz yoz. Faqat JSON formatda qaytar, boshqa hech narsa yozma. Telefon raqamni tog'ri kiritilishi bo'shliqlar bo'lmasligi 998 bilan boshlanishi men uchun juda ham muhim va bu yerda ortiqcha narsalar hech qachon ishlatilmasligi kerak. transport tog'ri aniqlanishi men uchun muhim."
                    )
                },
                {"role": "user", "content": text.strip()}
            ],
            temperature=0.2
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")
        return None



def detect_A_convert_text_to_json(text: str) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                 {
                    "role": "system",
                    "content": "Siz faqat quyidagi JSON formatida javob beradigan bot siz:\n{\n  \"fromARegion\": \"Viloyat nomi yoki Davlat nomi\",\n  \"fromADistrict\": \"Tuman/Shahar nomi\"}.\n- Agar joy Oʻzbekistonda boʻlsa, faqat viloyat va shahar/tuman nomlarini aniq ko‘rsat.\n- Agar joy Oʻzbekistondan tashqarida boʻlsa fromARegion uchun faqat davlat nomini yoz (masalan, \"Qirgʻiziston respublikasi\" yoki \"Rossiya federatsiyasi\") fromADistinct uchun berilgan viloyat va shahar/tuman nomlarini aniq ko‘rsat.\n- Har doim aniq JSON formatda qaytar, ortiqcha so‘zlar ishlatma Har doim aniq JSON formatda qaytar, ortiqcha so‘zlar ishlatma, aniqlay olmasang null qiymatlar qo‘yilishi kerak. "
                },
                {"role": "user", "content": text}],
            temperature=0.2
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")
        return None

def detect_B_convert_text_to_json(text: str) -> Optional[str]:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                 {
                    "role": "system",
                    "content": "Siz faqat quyidagi JSON formatida javob beradigan bot siz:\n{\n  \"toBRegion\": \"Viloyat nomi yoki Davlat nomi\",\n  \"toBDistrict\": \"Tuman/Shahar nomi\"}.\n- Agar joy Oʻzbekistonda boʻlsa, faqat viloyat va shahar/tuman nomlarini aniq ko‘rsat.\n- Agar joy Oʻzbekistondan tashqarida boʻlsa toBRegion uchun faqat davlat nomini yoz (masalan, \"Qirgʻiziston respublikasi\" yoki \"Rossiya federatsiyasi\"), toBDistrict uchun berilgan viloyat va shahar/tuman nomlarini aniq ko‘rsat.\n- Har doim aniq JSON formatda qaytar, ortiqcha so‘zlar ishlatma, aniqlay olmasang null qiymatlar qo‘yilishi kerak. "
                },
                {"role": "user", "content": text}],
            temperature=0.2
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")
        return None


def executeData(conn, corrected_names, phone, word_list, text):
    destinationARegion = ""
    destinationADistinct = ""
    destinationBRegion = ""
    destinationBDistinct = ""

    #######################################################################################################
    # a regionlardan to'liq lokatsiyani aniqlashga harakat qilib ko'rish 
    # Extract "from" column from corrected_names
    try:
        fromVal = corrected_names['from']
    except AttributeError:
        fromVal = ""

    if fromVal == "":
        # complete it with ChatGPT 
        print("❌ No matching region found.")
        return

    search_result = search_by_region(conn, fromVal)

    # print("\n📍 FOUND WORDS:")
    # print(search_result["found_words"])

    # print("\n❌ NOT FOUND WORDS:")
    # print(search_result["not_found_words"])

    # print("\n📦 RESULTS:")
    for row in search_result["results"]:
        # print(f"{row['name_uz']} | {row['name_cy']} | {row['name_ru']}")
        destinationARegion = row["name_uz"]


    if (len(search_result["not_found_words"]) != 0):
        queryDistinct = " ".join(search_result["not_found_words"])
        
        result = search_by_district(conn, queryDistinct)

        # print(result)

        if result:
            # print("\n📍 RESULT:")
            # print(
            #     f"""{result['location_distinct_uz'] or ''} - {result['location_distinct_cy'] or ''} | {result['location_distinct_ru'] or ''} | 
            #     {result['location_region_uz'] or ''} | {result['location_region_cy'] or ''} | {result['location_region_ru'] or ''}"""
            # )

            destinationARegion = result["location_region_uz"]
            destinationADistinct = result["location_distinct_uz"]
            
        # else:
            # print("❌ No matching district found.")

    #######################################################################################################
    # b regionlardan to'liq lokatsiyani aniqlashga harakat qilib ko'rish 
    # Extract "to" column from corrected_names
    try:
        toVal = corrected_names['to']
    except AttributeError:
        toVal = ""

    if toVal == "":
        # complete it with ChatGPT 
        print("❌ No matching region found.")
        import sys
        sys.exit(0)

    search_result = search_by_region(conn, toVal)

    # print("\n📍 FOUND WORDS:")
    # print(search_result["found_words"])

    # print("\n❌ NOT FOUND WORDS:")
    # print(search_result["not_found_words"])

    # print("\n📦 RESULTS:")
    for row in search_result["results"]:
        # print(f"{row['name_uz']} | {row['name_cy']} | {row['name_ru']}")
        destinationBRegion = row["name_uz"]


    if (len(search_result["not_found_words"]) != 0):
        queryDistinct = " ".join(search_result["not_found_words"])

        result = search_by_district(conn, queryDistinct)

        # print(result)

        if result:
            # print("\n📍 RESULT:")
            # print(
            #     f"""{result['location_distinct_uz'] or ''} - {result['location_distinct_cy'] or ''} | {result['location_distinct_ru'] or ''} | 
            #     {result['location_region_uz'] or ''} | {result['location_region_cy'] or ''} | {result['location_region_ru'] or ''}"""
            # )

            destinationBRegion = result["location_region_uz"]
            destinationBDistinct = result["location_distinct_uz"]
            
        # else:
            # print("❌ No matching district found.")

    if (destinationARegion == ""):
        fromVal = corrected_names['from']
        if (fromVal == ""): 
            print("❌ No matching region found.")
            return
        
        result = detect_A_convert_text_to_json(fromVal)
        destinationARegion = json.loads(result).get("fromARegion", "")
        destinationADistinct = json.loads(result).get("fromADistrict", "")

        if (destinationARegion == ""):
            print("❌ No matching region found.")
            return
    
    if (destinationBRegion == ""):
        toVal = corrected_names['to']
        if (toVal == ""): 
            print("❌ No matching region found.")
            return
        
        result = detect_B_convert_text_to_json(toVal)
        destinationBRegion = json.loads(result).get("toBRegion", "")
        destinationBDistinct = json.loads(result).get("toBDistrict", "")

        if (destinationBRegion == ""):
            print("❌ No matching region found.")
            return
        
    
    output = {
        "destinationARegion": destinationARegion,
        "destinationADistinct": destinationADistinct,
        "destinationBRegion": destinationBRegion,
        "destinationBDistinct": destinationBDistinct,
        "phone": phone,
        "comment": text,
        "transportType": corrected_names['transport'],
    }

    generated_json = json.dumps(output, ensure_ascii=False)
    print(generated_json)

    send_request(output, text)

    return generated_json

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

# def transform_json(input_json, comment: str):
#     if isinstance(input_json, list):  # If input is a list of objects
#         return [transform_json(item, comment) for item in input_json]
    
#     if (input_json.get("phone", "") == "" or input_json.get("phone", "") == "998" or input_json.get("phone", "") == None): 
#         return {}
    

#     return {
#         "destinationARegion": input_json.get("fromARegion", ""),
#         "destinationADistinct": input_json.get("fromADistrict", ""),
#         "destinationBRegion": input_json.get("toBRegion", ""),
#         "destinationBDistinct": input_json.get("toBDistrict", ""),
#         "transportType": input_json.get("transport", ""),
#         "comment": comment,
#         "phone": input_json.get("phone", "")
#     }

def findTransportType(text):
    words = ["Tent", "тентовка", "тент", "Ref", ""]
    message = "I am learning python programming."

    A = ahocorasick.Automaton()
    for idx, word in enumerate(words):
        A.add_word(word, (idx, word))
    A.make_automaton()

    found_words = set()
    for end_index, (idx, word) in A.iter(message.lower()):
        found_words.add(word)

    print(list(found_words))


def send_request(json_data, comment: str):
    url = "https://api.e-yuk.uz//cargo/create"  # Replace with actual API URL
    headers = {"Content-Type": "application/json"}

    if isinstance(json_data, list):
        for item in json_data:
            response = requests.post(url, headers=headers, json=item)
            # print(f"📤 Sending: {transform_json(item, comment)}")
            # print(f"📩 Response: {response.status_code}, {response.text}")
    else:
        response = requests.post(url, headers=headers, json=json_data)
        # print(f"📤 Sending: {transform_json(json_data, comment)}")
        # print(f"📩 Response: {response.status_code}, {response.text}")

async def executeText(pool, sender_id, channel, conn, text: str) -> dict:
    start_time = time.perf_counter()

    # Tekstni xato yozgan bo'lsa tog'ri so'zga o'girish
    word_list = load_word_list("word_list.txt")

    result = convert_text_to_json(text)
    corrected_names = correct_region_names_in_text(result, word_list)
    
    try:
        parsed_data = json.loads(corrected_names)
    except Exception as e:
        print(f"❌ Error: {e}", corrected_names)
        with open("conclusions.txt", "a", encoding='utf-8') as f:
            f.write(f"{time.asctime()}: Error: {e}, text: {text}\n")
        return ""

    phone = ""
    if isinstance(parsed_data, list):
        for item in parsed_data:
            # Ohirgi topilgan phoneni xotirada saqlab datani sartirovka qilish uchun uni ishlatish.
            if (item.get("phone", "") != "" and item.get("phone", "") != "998" and item.get("phone", "") != None): 
                phone = item.get("phone", "")
                break

        for item in parsed_data:
            # Ohirgi topilgan phoneni xotirada saqlab datani sartirovka qilish uchun uni ishlatish.
            message_json = executeData(conn, item, phone, word_list, text)

            if (message_json and message_json != ""):
                await save_to_db(pool, sender_id, text, message_json, channel)
    elif isinstance(parsed_data, dict):
        if (parsed_data.get("from", "") == "" or parsed_data.get("from", "") == "N/A" or parsed_data.get("to", "") == "" or parsed_data.get("to", "") == "N/A"):
            return
        
        message_json = executeData(conn, parsed_data, parsed_data.get("phone", ""), word_list, text)
        if (message_json and message_json != ""):
            await save_to_db(pool, sender_id, text, message_json, channel)
    else:
        print("❌ Unexpected data format:", parsed_data)


    

    # try:
    #     response = client.chat.completions.create(
    #         model="gpt-4o-mini",
    #         messages=[
    #              {
    #                 "role": "system",
    #                 "content": "Siz faqat quyidagi JSON formatida javob beradigan bot siz:\n{\n  \"fromARegion\": \"Viloyat nomi yoki Davlat nomi\",\n  \"fromADistrict\": \"Tuman/Shahar nomi yoki null\",\n  \"toBRegion\": \"Viloyat nomi yoki Davlat nomi\",\n  \"toBDistrict\": \"Tuman/Shahar nomi yoki null\",\n  \"transport\": \"Transport turi\",\n  \"phone\": \"Telefon raqami\"\n}.\n- Agar joy Oʻzbekistonda boʻlsa, faqat viloyat va shahar/tuman nomlarini aniq ko‘rsat.\n- Agar joy Oʻzbekistondan tashqarida boʻlsa, faqat davlat nomini yoz (masalan, \"Qirgʻiziston respublikasi\" yoki \"Rossiya federatsiyasi\").\n- Har doim aniq JSON formatda qaytar, ortiqcha so‘zlar ishlatma. Telefon raqamni tog'ri kiritilishi men uchun juda ham muhim va bu yerda ortiqcha narsalar hech qachon ishlatilmasligi kerak. {phone: '998917972385'}"
    #             },
    #             {"role": "user", "content": text}],
    #         temperature=0.2
    #     )

    #     if not response.choices or not response.choices[0].message.content:
    #         return None  

    #     response_text = response.choices[0].message.content.strip()
        
    #     try:
    #         comment = text

    #         generated_json = json.loads(response_text)

    #         end_time = time.perf_counter()

    #         elapsed_ms = (end_time - start_time) * 1000  # Convert to milliseconds
    #         print(f"chatgpt took {elapsed_ms:.2f} ms")
            
    #         # # print("Comment:", comment)
    #         send_request(generated_json, comment)
    #     except json.JSONDecodeError:
    #         # print(f"⚠️ OpenAI returned invalid JSON:\n{response_text}")
    #         return None
            
    #     if "phone" in generated_json and isinstance(generated_json["phone"], str):
    #         if generated_json["phone"].startswith("+998"):
    #             generated_json["phone"] = generated_json["phone"][1:]  
    #         elif not generated_json["phone"].startswith("998"):
    #             generated_json["phone"] = "998" + generated_json["phone"]

    #     return generated_json

    # except Exception as e:
        # print(f"❌ OpenAI Error: {str(e)}")
        return None

async def main():
    try:
        # SQL Connection
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            dbname="postgres",
            user="postgres",
            password="SardorBugun1taRedBullOldi!#"
        )
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

            # only with lowercase letters
            if any(word in text.lower() for word in [
                "yopildi", 
                "yopildimi", 
                "reklama", 
                "tarqatmang", 
                "boshqa yuklar:", 
                "aloqaga chiqish", 
                "xush kelibsiz"
            ]):
                return

            if await message_exists_text(pool, sender_id, text):
                print(f"⚠️ Duplicate skipped: [{channel}] {sender_id}")
                return

            await save_to_db(pool, sender_id, text, "", channel)

            await executeText(pool, sender_id, channel, conn, text)

        await client.start(PHONE_NUMBER)

        # for channel in CHANNELS:
        #     async for message in client.iter_messages(channel, limit=10):
        #         if not message.text:
        #             continue  

        #         sender_id = message.sender_id
        #         text = message.text

        #         if await message_exists_text(pool, sender_id, text):
        #             continue  

        #         executeText(pool, sender_id, channel, conn, text)
                

        # print("✅ Listening for new messages...")
        await client.run_until_disconnected()
        await pool.close()
    except asyncio.CancelledError:
        print("⚡ Bot cancelled (maybe Ctrl+C)")
    except KeyboardInterrupt:
        print("🛑 Bot manually stopped by keyboard")


asyncio.run(main())
