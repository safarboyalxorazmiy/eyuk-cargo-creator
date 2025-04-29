import openai
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # .env fayldan API kalitni yuklaydi
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
                        '  "transport": "Transport turi misol"\n'
                        "}\n\n"
                        "Faqat JSON formatda qaytar, boshqa hech narsa yozma."
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

# Test qilish
if __name__ == "__main__":
    result = convert_text_to_json("Bo'kadan Qarshiga 5 tonna yuk bor 93 608 01 02")
    if result:
        print("✅ JSON natija:", result)
