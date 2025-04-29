from deep_translator import GoogleTranslator

def main():
    translated = GoogleTranslator(source='uz', target='ru').translate("Toshkent")
    print(translated)  # Output: Bonjour

if __name__ == "__main__":
    main()

