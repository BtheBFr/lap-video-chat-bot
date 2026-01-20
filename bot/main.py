import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage  # ← ВАЖНО!
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv

from database import db

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
        InlineKeyboardButton("👥 Все пользователи", callback_data="admin_all_users"),
        InlineKeyboardButton("🚫 Забанить по ID", callback_data="admin_ban"),
        InlineKeyboardButton("✅ Разбанить по ID", callback_data="admin_unban"),
        InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh")
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
            "👨‍💻 Панель администратора Lap Video Chat",
            reply_markup=get_admin_keyboard()
        )
    else:
        # Проверяем в базе
        user = await db.get_user(user_id)
        
        if user:
            status = user.get("status")
            if status == "approved":
                await message.answer(
                    "🏠 Добро пожаловать в Lap Video Chat Bot!",
                    reply_markup=get_user_menu()
                )
            elif status == "banned":
                await message.answer("🚫 Вы заблокированы в системе!")
            else:
                await message.answer("⏳ Ваша заявка на рассмотрении...")
        else:
            # Новый пользователь
            await message.answer(
                "👋 Добро пожаловать в Lap Video Chat Bot!\n\n"
                "📞 Для доступа необходимо поделиться номером телефона.\n"
                "📋 После этого администратор рассмотрит вашу заявку.",
                reply_markup=get_phone_keyboard()
            )

@dp.message_handler(commands=['admin'], user_id=ADMIN_IDS)
async def cmd_admin(message: types.Message):
    await message.answer(
        "👨‍💻 Панель администратора",
        reply_markup=get_admin_keyboard()
    )

@dp.message_handler(commands=['stats'], user_id=ADMIN_IDS)
async def cmd_stats(message: types.Message):
    users = await db.get_all_users()
    pending = len([u for u in users if u["status"] == "pending"])
    approved = len([u for u in users if u["status"] == "approved"])
    banned = len([u for u in users if u["status"] == "banned"])
    
    stats_text = (
        "📊 Статистика бота:\n"
        f"👤 Всего пользователей: {len(users)}\n"
        f"⏳ Ожидают: {pending}\n"
        f"✅ Одобрено: {approved}\n"
        f"🚫 Забанено: {banned}"
    )
    await message.answer(stats_text)

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
    
    # Сохраняем в базу
    success, result = await db.create_user(
        telegram_id=user_id,
        phone=phone_number,
        full_name=full_name or message.from_user.full_name,
        username=message.from_user.username
    )
    
    if success:
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📨 НОВАЯ ЗАЯВКА!\n\n"
                    f"👤 Имя: {full_name}\n"
                    f"📱 Телефон: +{phone_number}\n"
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
            "✅ Спасибо! Номер получен.\n"
            "⏳ Ожидайте одобрения администратора.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            f"❌ Ошибка: {result}",
            reply_markup=types.ReplyKeyboardRemove()
        )

# ==================== ОБРАБОТКА КНОПОК АДМИНА ====================
@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[1])
    admin_id = callback_query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    # Обновляем статус в базе
    success = await db.update_user_status(user_id, "approved")
    
    if success:
        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            "🎉 ВАША ЗАЯВКА ОДОБРЕНА!\n\n"
            "Добро пожаловать в Lap Video Chat Bot!\n"
            "Теперь вам доступны все функции.",
            reply_markup=get_user_menu()
        )
        
        # Получаем информацию о пользователе
        user = await db.get_user(user_id)
        user_name = user.get("full_name", "Пользователь") if user else "Пользователь"
        
        await callback_query.message.edit_text(
            f"✅ Пользователь {user_name} одобрен!\n"
            f"ID: {user_id}",
            reply_markup=None
        )
        await callback_query.answer("✅ Одобрено!")
    else:
        await callback_query.answer("❌ Ошибка базы данных!")

@dp.callback_query_handler(lambda c: c.data.startswith('reject_'))
async def reject_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[1])
    admin_id = callback_query.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    # Обновляем статус в базе
    success = await db.update_user_status(user_id, "rejected")
    
    if success:
        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            "❌ Ваша заявка отклонена администратором."
        )
        
        user = await db.get_user(user_id)
        user_name = user.get("full_name", "Пользователь") if user else "Пользователь"
        
        await callback_query.message.edit_text(
            f"❌ Заявка от {user_name} отклонена!\n"
            f"ID: {user_id}",
            reply_markup=None
        )
        await callback_query.answer("❌ Отклонено!")
    else:
        await callback_query.answer("❌ Ошибка!")

# ==================== АДМИН ПАНЕЛЬ ====================
@dp.callback_query_handler(lambda c: c.data == 'admin_requests')
async def show_requests(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    pending_users = await db.get_pending_users()
    
    if not pending_users:
        await callback_query.message.edit_text(
            "📋 Список заявок пуст.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    text = "📋 Ожидающие заявки:\n\n"
    for user in pending_users[:10]:  # Показываем первые 10
        text += (
            f"👤 {user.get('full_name', 'Без имени')}\n"
            f"📱 +{user.get('phone_number', 'Нет номера')}\n"
            f"🆔 {user['telegram_id']}\n"
            f"━━━━━━━━━━━━━━━━\n"
        )
    
    await callback_query.message.edit_text(
        text,
        reply_markup=get_admin_keyboard()
    )
    await callback_query.answer(f"Заявок: {len(pending_users)}")

@dp.callback_query_handler(lambda c: c.data == 'admin_all_users')
async def show_all_users(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    all_users = await db.get_all_users()
    
    if not all_users:
        await callback_query.message.edit_text(
            "👥 Пользователей пока нет.",
            reply_markup=get_admin_keyboard()
        )
        return
    
    text = "👥 Все пользователи:\n\n"
    for user in all_users[:15]:  # Показываем первые 15
        status_icon = "✅" if user["status"] == "approved" else "⏳" if user["status"] == "pending" else "🚫"
        text += (
            f"{status_icon} {user.get('full_name', 'Без имени')}\n"
            f"📱 +{user.get('phone_number', 'Нет')} | 🆔 {user['telegram_id']}\n"
            f"━━━━━━━━━━━━━━━━\n"
        )
    
    await callback_query.message.edit_text(
        text[:4000],  # Ограничение Telegram
        reply_markup=get_admin_keyboard()
    )
    await callback_query.answer(f"Всего: {len(all_users)}")

# ==================== МЕНЮ ПОЛЬЗОВАТЕЛЯ ====================
@dp.message_handler(lambda m: m.text == "📞 Чаты")
async def show_chats(message: types.Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user["status"] != "approved":
        await message.answer("❌ Доступ запрещен!")
        return
    
    await message.answer(
        "📞 Ваши чаты:\n\n"
        "Эта функция будет доступна после настройки системы звонков.\n"
        "Сейчас можно:\n"
        "• Просматривать историю звонков\n"
        "• Создавать новые чаты\n"
        "• Приглашать контакты"
    )

@dp.message_handler(lambda m: m.text == "👥 Контакты")
async def show_contacts(message: types.Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user["status"] != "approved":
        await message.answer("❌ Доступ запрещен!")
        return
    
    await message.answer(
        "👥 Управление контактами:\n\n"
        "1. Добавить контакт - отправьте номер телефона\n"
        "2. Импортировать из телефонной книги\n"
        "3. Поиск контактов\n\n"
        "📱 Чтобы добавить контакт, просто отправьте номер телефона в формате +79991234567"
    )

# ==================== ЗАПУСК БОТА ====================
async def on_startup(dp):
    logger.info("✅ Lap Video Chat Bot запущен!")
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Бот запущен и готов к работе!")
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

async def on_shutdown(dp):
    logger.info("Бот остановлен")

if __name__ == '__main__':
    from aiogram import executor
    
    logger.info("🚀 Запуск Lap Video Chat Bot...")
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
