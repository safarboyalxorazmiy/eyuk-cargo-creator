import json

# Either use the JSON filename directly (if script is alongside it):
json_path = 'districts.json'

# Or, if you must use a full path, make it raw or escape backslashes:
# json_path = r'C:\Users\Safarboy\Desktop\eyuk-python\myTeleg\districts.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

suffixes = [
    ' tumani', ' тумани',
    ' shahri', ' шаҳри',
    ' район', ' город'
]

names = set()
for item in data:
    for key in ('name_uz', 'name_oz', 'name_ru'):
        name = item.get(key, '').strip()
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        if name:
            names.add(name)

sorted_names = sorted(names, key=lambda s: s.lower())

with open('word_list.txt', 'w', encoding='utf-8') as f:
    for name in sorted_names:
        f.write(f"{name}\n")

print(f"Generated word_list.txt with {len(sorted_names)} entries.")
