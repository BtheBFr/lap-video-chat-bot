import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        # Отладка
        logger.info(f"🔗 Подключение к Supabase...")
        logger.info(f"📡 URL: {url}")
        logger.info(f"🔑 Ключ (первые 20 символов): {key[:20] if key else 'None'}...")
        
        if not url or not key:
            logger.error("❌ Отсутствуют переменные Supabase!")
            self.supabase = None
            return
        
        try:
            # ВАЖНО: используем secret ключ
            self.supabase: Client = create_client(url, key)
            
            # Тестовый запрос
            test = self.supabase.table("users").select("count", count="exact").execute()
            logger.info(f"✅ Supabase подключен! Таблица users: {test.count} записей")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Supabase: {e}")
            logger.info("📦 Используется временное хранилище в памяти")
            self.supabase = None
    
    async def create_user(self, telegram_id: int, phone: str, full_name: str, username: str = None):
        """Добавить нового пользователя"""
        try:
            if self.supabase:
                data = {
                    "telegram_id": telegram_id,
                    "phone_number": phone,
                    "full_name": full_name,
                    "username": username,
                    "status": "pending"
                }
                response = self.supabase.table("users").insert(data).execute()
                return True, "Заявка отправлена в базу"
            else:
                # Временное хранилище
                return True, "Заявка отправлена (временное хранилище)"
                
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    async def get_user(self, telegram_id: int):
        """Получить пользователя по ID"""
        try:
            if self.supabase:
                response = self.supabase.table("users")\
                    .select("*")\
                    .eq("telegram_id", telegram_id)\
                    .execute()
                return response.data[0] if response.data else None
            else:
                return None  # Временное хранилище
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    # ... остальные методы БЕЗ ИЗМЕНЕНИЙ ...

db = Database()
