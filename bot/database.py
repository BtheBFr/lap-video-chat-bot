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
        
        logger.info(f"🔗 Подключение к Supabase...")
        
        if not url or not key:
            logger.error("❌ Отсутствуют переменные Supabase!")
            self.supabase = None
            self.local_users = {}
            return
        
        try:
            self.supabase: Client = create_client(url, key)
            # Тестовый запрос
            test = self.supabase.table("users").select("count", count="exact").execute()
            logger.info(f"✅ Supabase подключен! Записей: {test.count}")
            self.local_users = {}
        except Exception as e:
            logger.error(f"❌ Ошибка Supabase: {e}")
            logger.info("📦 Используется временное хранилище")
            self.supabase = None
            self.local_users = {}
    
    async def create_user(self, telegram_id: int, phone: str, full_name: str, username: str = None):
        """Добавить нового пользователя"""
        try:
            # Проверяем есть ли уже
            existing = await self.get_user(telegram_id)
            if existing:
                return False, "Заявка уже отправлена"
            
            if self.supabase:
                data = {
                    "telegram_id": telegram_id,
                    "phone_number": phone,
                    "full_name": full_name,
                    "username": username,
                    "status": "pending"
                }
                response = self.supabase.table("users").insert(data).execute()
                return True, "Заявка отправлена"
            else:
                # Временное хранилище
                self.local_users[telegram_id] = {
                    "telegram_id": telegram_id,
                    "phone_number": phone,
                    "full_name": full_name,
                    "username": username,
                    "status": "pending"
                }
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
                return self.local_users.get(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    async def update_user_status(self, telegram_id: int, status: str):
        """Обновить статус пользователя"""
        try:
            if self.supabase:
                response = self.supabase.table("users")\
                    .update({"status": status})\
                    .eq("telegram_id", telegram_id)\
                    .execute()
                return True
            else:
                if telegram_id in self.local_users:
                    self.local_users[telegram_id]["status"] = status
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return False
    
    async def get_pending_users(self):
        """Получить всех пользователей со статусом pending"""
        try:
            if self.supabase:
                response = self.supabase.table("users")\
                    .select("*")\
                    .eq("status", "pending")\
                    .execute()
                return response.data
            else:
                return [u for u in self.local_users.values() if u.get("status") == "pending"]
        except Exception as e:
            logger.error(f"Ошибка получения pending пользователей: {e}")
            return []
    
    async def get_all_users(self):
        """Получить всех пользователей"""
        try:
            if self.supabase:
                response = self.supabase.table("users")\
                    .select("*")\
                    .order("created_at", desc=True)\
                    .execute()
                return response.data
            else:
                return list(self.local_users.values())
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
    async def ban_user(self, telegram_id: int):
        """Забанить пользователя"""
        return await self.update_user_status(telegram_id, "banned")
    
    async def unban_user(self, telegram_id: int):
        """Разбанить пользователя"""
        return await self.update_user_status(telegram_id, "approved")

db = Database()
