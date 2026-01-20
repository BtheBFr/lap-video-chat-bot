import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
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

# ==================== СОСТОЯНИЯ ====================
class AdminStates(StatesGroup):
    waiting_ban_id = State()
    waiting_unban_id = State()

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
        InlineKeyboardButton("🚫 Забанить", callback_data="admin_ban"),
        InlineKeyboardButton("✅ Разбанить", callback_data="admin_unban"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="user_main_menu")
    )

def get_user_menu(user_is_admin=False):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📞 Чаты", callback_data="user_chats"),
        InlineKeyboardButton("👥 Контакты", callback_data="user_contacts"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="user_settings"),
        InlineKeyboardButton("🆘 Помощь", callback_data="user_help")
    )
    if user_is_admin:
        keyboard.add(InlineKeyboardButton("👨‍💻 Админ панель", callback_data="admin_panel"))
    return keyboard

# ==================== КОМАНДЫ ====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
    
    if is_admin:
        # Админ видит и меню и админ-панель
        await message.answer(
            "👋 Добро пожаловать, администратор!\n\n"
            "Вы можете использовать обычные функции или перейти в админ-панель.",
            reply_markup=get_user_menu(user_is_admin=True)
        )
        return
    
    # Проверяем есть ли пользователь
    user = await db.get_user(user_id)
    
    if user:
        status = user.get("status")
        if status == "approved":
            await message.answer(
                "🏠 Добро пожаловать в Lap Video Chat Bot!",
                reply_markup=get_user_menu(user_is_admin=False)
            )
        elif status == "banned":
            await message.answer("🚫 Вы заблокированы в системе!")
        elif status == "pending":
            await message.answer(
                "⏳ Ваша заявка уже отправлена и находится на рассмотрении.\n"
                "Ожидайте одобрения администратора."
            )
        else:
            await message.answer(
                "❓ Неизвестный статус. Обратитесь к администратору.",
                reply_markup=get_user_menu(user_is_admin=False)
            )
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

# ==================== ОБРАБОТКА НОМЕРА ТЕЛЕФОНА ====================
@dp.message_handler(content_types=['contact'])
async def process_contact(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        await message.answer(
            "Вы администратор! Используйте меню ниже.",
            reply_markup=get_user_menu(user_is_admin=True)
        )
        return
    
    # Проверяем есть ли уже заявка
    existing_user = await db.get_user(user_id)
    if existing_user:
        status = existing_user.get("status")
        if status == "pending":
            await message.answer(
                "⏳ Ваша заявка уже отправлена и ожидает рассмотрения.",
                reply_markup=get_user_menu(user_is_admin=False)
            )
            return
        elif status == "approved":
            await message.answer(
                "✅ Вы уже одобрены! Используйте меню ниже.",
                reply_markup=get_user_menu(user_is_admin=False)
            )
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
                    f"📛 @{message.from_user.username or 'нет'}",
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
            reply_markup=get_user_menu(user_is_admin=False)
        )
    else:
        await message.answer(
            f"❌ Ошибка: {result}",
            reply_markup=get_user_menu(user_is_admin=False)
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
        try:
            await bot.send_message(
                user_id,
                "🎉 ВАША ЗАЯВКА ОДОБРЕНА!\n\n"
                "Добро пожаловать в Lap Video Chat Bot!\n"
                "Теперь вам доступны все функции.",
                reply_markup=get_user_menu(user_is_admin=False)
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
        
        # Получаем информацию о пользователе
        user = await db.get_user(user_id)
        user_name = user.get("full_name", "Пользователь") if user else "Пользователь"
        
        await callback_query.message.edit_text(
            f"✅ Пользователь одобрен!\n"
            f"👤 Имя: {user_name}\n"
            f"🆔 ID: {user_id}",
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
        try:
            await bot.send_message(
                user_id,
                "❌ Ваша заявка отклонена администратором."
            )
        except:
            pass
        
        user = await db.get_user(user_id)
        user_name = user.get("full_name", "Пользователь") if user else "Пользователь"
        
        await callback_query.message.edit_text(
            f"❌ Заявка отклонена!\n"
            f"👤 Имя: {user_name}\n"
            f"🆔 ID: {user_id}",
            reply_markup=None
        )
        await callback_query.answer("❌ Отклонено!")
    else:
        await callback_query.answer("❌ Ошибка!")

# ==================== АДМИН ПАНЕЛЬ ====================
@dp.callback_query_handler(lambda c: c.data == 'admin_panel')
async def admin_panel(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    await callback_query.message.edit_text(
        "👨‍💻 Панель администратора Lap Video Chat",
        reply_markup=get_admin_keyboard()
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_requests')
async def show_requests(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    pending_users = await db.get_pending_users()
    
    if not pending_users:
        text = "📋 Список заявок пуст."
    else:
        text = "📋 Ожидающие заявки:\n\n"
        for user in pending_users[:10]:
            text += (
                f"👤 {user.get('full_name', 'Без имени')}\n"
                f"📱 +{user.get('phone_number', 'Нет номера')}\n"
                f"🆔 {user.get('telegram_id', 'Нет ID')}\n"
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
        text = "👥 Пользователей пока нет."
    else:
        text = "👥 Все пользователи:\n\n"
        for user in all_users[:15]:
            status_icon = "✅" if user.get("status") == "approved" else "⏳" if user.get("status") == "pending" else "🚫"
            text += (
                f"{status_icon} {user.get('full_name', 'Без имени')}\n"
                f"📱 +{user.get('phone_number', 'Нет')} | 🆔 {user.get('telegram_id', 'Нет')}\n"
                f"━━━━━━━━━━━━━━━━\n"
            )
    
    await callback_query.message.edit_text(
        text[:4000],
        reply_markup=get_admin_keyboard()
    )
    await callback_query.answer(f"Всего: {len(all_users)}")

@dp.callback_query_handler(lambda c: c.data == 'admin_ban')
async def start_ban_user(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    await AdminStates.waiting_ban_id.set()
    await callback_query.message.edit_text(
        "🚫 Введите ID пользователя для блокировки:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")
        )
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_unban')
async def start_unban_user(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    await AdminStates.waiting_unban_id.set()
    await callback_query.message.edit_text(
        "✅ Введите ID пользователя для разблокировки:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")
        )
    )
    await callback_query.answer()

@dp.message_handler(state=AdminStates.waiting_ban_id)
async def process_ban_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        success = await db.ban_user(user_id)
        
        if success:
            await message.answer(f"✅ Пользователь {user_id} заблокирован!")
            
            # Уведомляем пользователя если возможно
            try:
                await bot.send_message(user_id, "🚫 Вы были заблокированы администратором.")
            except:
                pass
        else:
            await message.answer(f"❌ Не удалось заблокировать пользователя {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.")
    finally:
        await state.finish()

@dp.message_handler(state=AdminStates.waiting_unban_id)
async def process_unban_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        success = await db.unban_user(user_id)
        
        if success:
            await message.answer(f"✅ Пользователь {user_id} разблокирован!")
            
            # Уведомляем пользователя если возможно
            try:
                await bot.send_message(user_id, "✅ Вы были разблокированы администратором.")
            except:
                pass
        else:
            await message.answer(f"❌ Не удалось разблокировать пользователя {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.")
    finally:
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'admin_stats', state="*")
async def admin_stats(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    users = await db.get_all_users()
    pending = len([u for u in users if u.get("status") == "pending"])
    approved = len([u for u in users if u.get("status") == "approved"])
    banned = len([u for u in users if u.get("status") == "banned"])
    
    stats_text = (
        "📊 Статистика бота:\n"
        f"👤 Всего пользователей: {len(users)}\n"
        f"⏳ Ожидают: {pending}\n"
        f"✅ Одобрено: {approved}\n"
        f"🚫 Забанено: {banned}"
    )
    
    await callback_query.message.edit_text(
        stats_text,
        reply_markup=get_admin_keyboard()
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'cancel_action', state="*")
async def cancel_action(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("❌ Нет прав!")
        return
    
    await state.finish()
    await callback_query.message.edit_text(
        "👨‍💻 Панель администратора Lap Video Chat",
        reply_markup=get_admin_keyboard()
    )
    await callback_query.answer("❌ Отменено")

@dp.callback_query_handler(lambda c: c.data == 'user_main_menu')
async def user_main_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    is_admin = user_id in ADMIN_IDS
    
    await callback_query.message.edit_text(
        "🏠 Главное меню" if not is_admin else "👋 Добро пожаловать, администратор!",
        reply_markup=get_user_menu(user_is_admin=is_admin)
    )
    await callback_query.answer()

# ==================== МЕНЮ ПОЛЬЗОВАТЕЛЯ ====================
@dp.callback_query_handler(lambda c: c.data == 'user_chats')
async def user_chats(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user.get("status") != "approved":
        await callback_query.answer("❌ Доступ запрещен!")
        return
    
    await callback_query.message.edit_text(
        "📞 Ваши чаты:\n\n"
        "Эта функция будет доступна после настройки системы звонков.\n"
        "Сейчас можно:\n"
        "• Просматривать историю звонков\n"
        "• Создавать новые чаты\n"
        "• Приглашать контактов",
        reply_markup=get_user_menu(user_is_admin=user_id in ADMIN_IDS)
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'user_contacts')
async def user_contacts(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user.get("status") != "approved":
        await callback_query.answer("❌ Доступ запрещен!")
        return
    
    await callback_query.message.edit_text(
        "👥 Управление контактами:\n\n"
        "1. Добавить контакт - отправьте номер телефона\n"
        "2. Импортировать из телефонной книги\n"
        "3. Поиск контактов\n\n"
        "📱 Чтобы добавить контакт, просто отправьте номер телефона в формате +79991234567",
        reply_markup=get_user_menu(user_is_admin=user_id in ADMIN_IDS)
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'user_settings')
async def user_settings(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user.get("status") != "approved":
        await callback_query.answer("❌ Доступ запрещен!")
        return
    
    await callback_query.message.edit_text(
        "⚙️ Настройки:\n\n"
        "• Уведомления\n"
        "• Конфиденциальность\n"
        "• Язык интерфейса\n"
        "• Очистить историю",
        reply_markup=get_user_menu(user_is_admin=user_id in ADMIN_IDS)
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'user_help')
async def user_help(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        "🆘 Помощь:\n\n"
        "• Как начать звонок?\n"
        "• Как добавить контакт?\n"
        "• Проблемы со звуком/видео\n"
        "• Техническая поддержка: @LapVideoChatSupport",
        reply_markup=get_user_menu(user_is_admin=callback_query.from_user.id in ADMIN_IDS)
    )
    await callback_query.answer()

# ==================== ЗАПУСК БОТА ====================
async def on_startup(dp):
    logger.info("✅ Lap Video Chat Bot запущен!")
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
