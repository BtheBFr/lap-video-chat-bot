import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Временное хранилище (заменим на Supabase позже)
pending_requests = {}  # {user_id: {"phone": "...", "name": "..."}}
users = {}  # {user_id: {"status": "approved/banned", "phone": "...", "name": "..."}}

# ==================== СОСТОЯНИЯ ====================
class UserStates(StatesGroup):
    waiting_for_approval = State()
    main_menu = State()

# ==================== КЛАВИАТУРЫ ====================
def get_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📱 Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_admin_keyboard():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📋 Заявки", callback_data="admin_requests"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton("🚫 Забанить", callback_data="admin_ban"),
        InlineKeyboardButton("✅ Разбанить", callback_data="admin_unban")
    )

def get_user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            ["📞 Чаты", "👥 Контакты"],
            ["⚙️ Настройки", "🆘 Помощь"]
        ],
        resize_keyboard=True
    )

# ==================== КОМАНДЫ ====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        # Админ
        await message.answer(
            "👨‍💻 Панель администратора",
            reply_markup=get_admin_keyboard()
        )
    elif user_id in users:
        # Уже зарегистрированный пользователь
        if users[user_id]["status"] == "approved":
            await message.answer(
                "🏠 Главное меню",
                reply_markup=get_user_menu()
            )
        elif users[user_id]["status"] == "banned":
            await message.answer("🚫 Вы заблокированы!")
        else:
            await message.answer("⏳ Ваша заявка на рассмотрении...")
    else:
        # Новый пользователь
        await message.answer(
            "👋 Добро пожаловать в Lap Video Chat Bot!\n\n"
            "Для доступа необходимо поделиться номером телефона:",
            reply_markup=get_phone_keyboard()
        )

@dp.message_handler(commands=['admin'], user_id=ADMIN_IDS)
async def cmd_admin(message: types.Message):
    await message.answer(
        "👨‍💻 Панель администратора",
        reply_markup=get_admin_keyboard()
    )

# ==================== ОБРАБОТКА НОМЕРА ТЕЛЕФОНА ====================
@dp.message_handler(content_types=['contact'])
async def process_contact(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        await message.answer("Админам не нужно регистрироваться!")
        return
    
    contact = message.contact
    phone_number = contact.phone_number
    full_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    
    # Сохраняем заявку
    pending_requests[user_id] = {
        "phone": phone_number,
        "name": full_name or message.from_user.full_name,
        "username": message.from_user.username
    }
    
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📨 Новая заявка!\n\n"
                f"👤 Имя: {full_name}\n"
                f"📱 Телефон: {phone_number}\n"
                f"🆔 ID: {user_id}\n"
                f"📛 @{message.from_user.username}",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
                )
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
    
    await message.answer(
        "✅ Номер телефона получен!\n"
        "⏳ Ожидайте одобрения администратора.",
        reply_markup=types.ReplyKeyboardRemove()
    )

# ==================== ОБРАБОТКА КНОПОК АДМИНА ====================
@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[1])
    
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    if user_id in pending_requests:
        user_data = pending_requests.pop(user_id)
        users[user_id] = {
            "status": "approved",
            "phone": user_data["phone"],
            "name": user_data["name"]
        }
        
        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            "🎉 Ваша заявка одобрена!\n"
            "Добро пожаловать в Lap Video Chat Bot!",
            reply_markup=get_user_menu()
        )
        
        await callback_query.message.edit_text(
            f"✅ Пользователь {user_data['name']} одобрен!",
            reply_markup=None
        )
        await callback_query.answer("✅ Одобрено!")
    else:
        await callback_query.answer("❌ Заявка не найдена!")

@dp.callback_query_handler(lambda c: c.data.startswith('reject_'))
async def reject_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[1])
    
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    if user_id in pending_requests:
        user_data = pending_requests.pop(user_id)
        await bot.send_message(user_id, "❌ Ваша заявка отклонена.")
        
        await callback_query.message.edit_text(
            f"❌ Заявка от {user_data['name']} отклонена!",
            reply_markup=None
        )
        await callback_query.answer("❌ Отклонено!")

# ==================== МЕНЮ ПОЛЬЗОВАТЕЛЯ ====================
@dp.message_handler(lambda m: m.text == "📞 Чаты")
async def show_chats(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users or users[user_id]["status"] != "approved":
        await message.answer("❌ Доступ запрещен!")
        return
    
    await message.answer("📞 Ваши чаты:\n(функция в разработке)")

@dp.message_handler(lambda m: m.text == "👥 Контакты")
async def show_contacts(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users or users[user_id]["status"] != "approved":
        await message.answer("❌ Доступ запрещен!")
        return
    
    await message.answer("👥 Ваши контакты:\n(функция в разработке)")

# ==================== ЗАПУСК БОТА ====================
async def on_startup(dp):
    logger.info("Бот запущен!")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Бот запущен и готов к работе!")
        except:
            pass

async def on_shutdown(dp):
    logger.info("Бот остановлен!")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
