import requests
import random
import time

# Example browsers and platforms
BROWSERS = [
    ("Chrome", "135.0.0.0"),
    ("Firefox", "126.0"),
    ("Edge", "124.0.2478.97"),
    ("Safari", "17.5")
]

PLATFORMS = [
    "Windows",
    "Macintosh",
    "Linux"
]

# Example random words
WORDS = [
    "Salom", "Dunyo", "Kitob", "Ohangaron", "Yangiobod", "Toshkent", 
    "Namangan", "Qarshi", "Surxondaryo", "Andijon", "Kitob", "Til", "Do'stlik",
    "Paxtakor", "Bog'", "Tabiat", "Fikr", "Muhabbat", "Yurak", "Qalb"
]

def get_random_headers():
    browser_name, browser_version = random.choice(BROWSERS)
    platform = random.choice(PLATFORMS)

    user_agent = f"Mozilla/5.0 ({platform}; x64) AppleWebKit/537.36 (KHTML, like Gecko) {browser_name}/{browser_version} Safari/537.36"

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,uz;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://tilmoch.ai",
        "Referer": "https://tilmoch.ai/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": user_agent,
        "sec-ch-ua": f"\"{browser_name}\";v=\"{browser_version}\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": f"\"{platform}\""
    }
    return headers

def get_guest_token():
    url = "https://auth.tahrirchi.uz/v1/guest"
    headers = get_random_headers()
    response = requests.post(url, headers=headers, json={})
    response.raise_for_status()
    data = response.json()

    return data["data"]["access_token"]

def translate_uzbek_to_russian_batch(text: str, access_token: str) -> str:
    url = "https://websocket.tahrirchi.uz/handle-batch"
    headers = get_random_headers()
    headers["Authorization"] = f"Bearer {access_token}"

    payload = {
        "jobs": [
            {
                "text": text,
                "id": random.randint(10000, 99999)  # Random id for each job
            }
        ],
        "source_lang": "uzn_Latn",
        "target_lang": "rus_Cyrl"
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    try:
        translated_text = data["sentences"][0]["translated"]
    except (KeyError, IndexError):
        translated_text = ""

    return translated_text

if __name__ == "__main__":
    access_token = get_guest_token()
    request_count = 0

    while True:
        # Pick random word
        random_word = random.choice(WORDS)

        # Translate it
        try:
            translated = translate_uzbek_to_russian_batch(random_word, access_token)
            request_count += 1
            print(f"[{request_count}] {random_word} -> {translated}")

        except Exception as e:
            print(f"Error: {e}")
            # Try to refresh token if error happens
            access_token = get_guest_token()

        # Random sleep between 0.5 to 2 seconds to act more like human
        time.sleep(random.uniform(0.5, 2.0))
