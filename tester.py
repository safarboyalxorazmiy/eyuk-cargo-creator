import openai

# Initialize OpenAI client
import os
from dotenv import load_dotenv

# OpenAI API Key
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Define the prompt
prompt = """
Convert the following text into a JSON object with the keys: fromA, fromB, phone, comment, and vehicle.
- Remove icons, emojis, and extra symbols.
- Ensure phone numbers follow the Uzbek format (if they don’t start with 998, prepend it).
- Extract relevant text while keeping the structure clean.

Text:  
ТОШКЕНТ - СУРХАНДАРЁ  
🚛 тент фура  
☎️ 944818106  
👤 Aloqaga_chiqish  
#SURXONDARYO  
Boshqa yuklar: @lorry_yuk_markazi
"""

# Call GPT to generate JSON
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)

# Print the generated JSON
generated_json = response.choices[0].message.content
print(generated_json)