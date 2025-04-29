import requests

def translate_uzbek_to_russian_batch(text: str) -> str:
    url = "https://websocket.tahrirchi.uz/handle-batch"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en,en-US;q=0.9,uz;q=0.8,ru;q=0.7",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDgwOTk3NzksImlhdCI6MTc0NTUwNzc3OSwic3ViIjoiZGI2YTYzMjktYWUyOS00ZTNkLTkyOGYtYWE1Y2MzM2JjZTBjIiwidHNpZCI6IiIsInR5cGUiOi0xfQ._y25tRlfCI6iJlY6_uGAUciq-FgN2fw7eI9Fu1Jz42U",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://tilmoch.ai",
        "Referer": "https://tilmoch.ai/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    payload = {
        "jobs": [
            {
                "text": text,
                "id": 10001
            }
        ],
        "source_lang": "uzn_Latn",
        "target_lang": "rus_Cyrl"
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    # Extract main translated text
    try:
        translated_text = data["sentences"][0]["translated"]
    except (KeyError, IndexError):
        translated_text = ""

    return translated_text

# Example usage
if __name__ == "__main__":
    text = "Ohangaron viloyati"
    result = translate_uzbek_to_russian_batch(text)
    print("Translated:", result)
