import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        self.supabase: Client = create_client(url, key)
        print("✅ База данных подключена!")
    
    async def create_user(self, telegram_id: int, phone: str, full_name: str, username: str = None):
        """Добавить нового пользователя"""
        try:
            # Проверяем, есть ли уже пользователь
            existing = await self.get_user(telegram_id)
            if existing:
                return False, "Пользователь уже существует"
            
            data = {
                "telegram_id": telegram_id,
                "phone_number": phone,
                "full_name": full_name,
                "username": username,
                "status": "pending"
            }
            response = self.supabase.table("users").insert(data).execute()
            return True, "Заявка отправлена"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    async def get_user(self, telegram_id: int):
        """Получить пользователя по ID"""
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .eq("telegram_id", telegram_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Database error: {e}")
            return None
    
    async def update_user_status(self, telegram_id: int, status: str):
        """Обновить статус пользователя"""
        try:
            response = self.supabase.table("users")\
                .update({"status": status})\
                .eq("telegram_id", telegram_id)\
                .execute()
            return True
        except Exception as e:
            print(f"Update error: {e}")
            return False
    
    async def get_pending_users(self):
        """Получить всех пользователей со статусом pending"""
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .eq("status", "pending")\
                .execute()
            return response.data
        except Exception as e:
            print(f"Get pending error: {e}")
            return []
    
    async def get_all_users(self):
        """Получить всех пользователей"""
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .order("created_at", desc=True)\
                .execute()
            return response.data
        except Exception as e:
            print(f"Get all error: {e}")
            return []
    
    async def ban_user(self, telegram_id: int):
        """Забанить пользователя"""
        try:
            response = self.supabase.table("users")\
                .update({"status": "banned"})\
                .eq("telegram_id", telegram_id)\
                .execute()
            return True
        except Exception as e:
            print(f"Ban error: {e}")
            return False
    
    async def unban_user(self, telegram_id: int):
        """Разбанить пользователя"""
        try:
            response = self.supabase.table("users")\
                .update({"status": "approved"})\
                .eq("telegram_id", telegram_id)\
                .execute()
            return True
        except Exception as e:
            print(f"Unban error: {e}")
            return False

# Создаем глобальный экземпляр БД
db = Database()
