import os
from dotenv import load_dotenv

load_dotenv()

print("=== 🐞 DEBUG ENVIRONMENT VARIABLES ===")
print(f"BOT_TOKEN: {'SET' if os.getenv('BOT_TOKEN') else 'NOT SET'}")
print(f"ADMIN_IDS: {os.getenv('ADMIN_IDS')}")
print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"SUPABASE_KEY: {os.getenv('SUPABASE_KEY')[:20]}..." if os.getenv('SUPABASE_KEY') else 'NOT SET')

# Проверяем начало ключа
key = os.getenv('SUPABASE_KEY', '')
if key:
    print(f"KEY starts with: {key[:30]}")
    print(f"KEY length: {len(key)} chars")
print("======================================")
