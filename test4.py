import difflib
import re
import openai
import os
import psycopg2
import json
import time
from psycopg2.extras import RealDictCursor
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

def correct_region_names_in_text(text: str, word_list: list, cutoff=0.7):
    if "'" in text:
        return text

    corrected_text = text
    candidates = set(re.findall(r"[^\s\d\W\-]+", text, flags=re.UNICODE))

    for word in candidates:
        match = difflib.get_close_matches(word, word_list, n=1, cutoff=cutoff)
        if match:
            corrected_text = re.sub(rf"\b{re.escape(word)}\b", match[0], corrected_text)

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
                        "from va to o'zgaruvchi qiymatlarida davlat nomlari, shahar, tuman va viloyat qatnashishi mumkin masalan Qozog'iston. Hech qanday ortiqcha emoji, belgilar(🇨🇳 kabi) ishlatilmasligi kerak faqat joylashuv yoki davlat nomini imloviy xatolarsiz yoz. Faqat JSON formatda qaytar, boshqa hech narsa yozma. Telefon raqamni tog'ri kiritilishi men uchun juda ham muhim va bu yerda ortiqcha narsalar hech qachon ishlatilmasligi kerak. transport tog'ri aniqlanishi men uchun muhim."
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


def executeData(corrected_names, phone, word_list):
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
        "transportType": corrected_names['transport'],
    }

    print(json.dumps(output, indent=4, ensure_ascii=False))


    # agar pustoy bo'lsa hammasini chatgptga qildirish.


if __name__ == "__main__":
    start_time = time.time()

    # SQL Connection
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        dbname="postgres",
        user="postgres",
        password="postgres"
    )

    # Tekstni xato yozgan bo'lsa tog'ri so'zga o'girish
    word_list = load_word_list("word_list.txt")

    original = """
    Samarqand alashankouga\nYuk mayiz 24tonna 3ta \nTent kerak srochna \n1500$ joyida beriladi\n970547577\n\nSamarqand xorgosga \nYuk mayiz 24tonna \nMashina kerak 3 ta srochna \n1600$ joyida beriladi \n970547577\n\nSurqandaryo Chexev\nYuk piyoz 22tonna\nTent kerak srochna \n2200$ Avans bor\n970547577\n\nShimkent - Moskova \nRef kerak 1 ta\nObshiy ves 35 tonna\nYuk sok yuklanadi\n2800$  Avans 1000$\n970547577\n\nКаратай Ташкент 23,070кг плашадка керек \nКаратай Ташкент 24340кг плашадка керек \nКаратай Ташкент 26,650кг тентовка керек \nКаратай Ангрен 26800кг тентовка плашатка керек\n700$ берилади \n970547577
    """

    corrected = correct_region_names_in_text(original, word_list)
    # print("🔍 Original:\n", original)
    # print("\n✅ Corrected:\n", corrected)

    # Tekstni chatgptga yuborish va a va b regionlarini aniqlash
    result = convert_text_to_json(original)

    
    # print("✅ JSON natija:", result)

    # Chatgpt bergan tekstni xato yozgan bo'lsa tog'ri so'zga o'girish
    corrected_names = correct_region_names_in_text(result, word_list)
    # print("✅ JSON natija corrected:", corrected_names)


    if corrected_names:
        parsed_data = json.loads(corrected_names)


    phone = ""
    if isinstance(parsed_data, list):
        for item in parsed_data:
            # Ohirgi topilgan phoneni xotirada saqlab datani sartirovka qilish uchun uni ishlatish.
            if (item.get("phone", "") != ""): 
                phone = item.get("phone", "")
            executeData(item, phone, word_list)
    elif isinstance(parsed_data, dict):
        print(parsed_data)
        executeData(parsed_data, parsed_data.get("phone", ""), word_list)
    else:
        print("❌ Unexpected data format:", parsed_data)



    conn.close()


                # executeData(item, word_list)
        # else:
        #     print(corrected_names)
            # executeData(corrected_names, word_list)

    end_time = time.time()
    spent_time = end_time - start_time

    print(f"Spent time: {spent_time:.2f} seconds")



