import logging
import os
import json
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

BOT_TOKEN = '
CHANNEL_ID = 
ADMIN_USER_ID = 
DRUMKIT_FILE_PATH = 
MESSAGE_TEXT = """
Спасибо за подписку! 🔥

Вот твой драмкит: [Название кита]

Надеюсь, он поможет тебе в творчестве!
Удачи! 🚀
"""
USER_DATA_FILE = 'user_data.json'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return {}
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {int(k): v for k, v in data.items()}
            else:
                 logger.warning(f"Обнаружен старый формат файла {USER_DATA_FILE}. Конвертирую в новый.")
                 new_data = {}
                 if isinstance(data, list):
                     for user_id in data:
                         new_data[int(user_id)] = {"username": None, "first_name": "Unknown", "added_at": datetime.datetime.now().isoformat()}
                 save_user_data(new_data)
                 return new_data

    except (json.JSONDecodeError, FileNotFoundError, ValueError, TypeError) as e:
        logger.error(f"Ошибка чтения файла {USER_DATA_FILE} или он пуст/поврежден ({e}). Создаем пустой словарь.")
        return {}

def save_user_data(user_data):
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            data_to_save = {str(k): v for k, v in user_data.items()}
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
    except IOError:
        logger.error(f"Не удалось записать данные в файл {USER_DATA_FILE}")

def add_or_update_user(user: Update.effective_user):
    user_data = load_user_data()
    user_id = user.id
    now = datetime.datetime.now().isoformat()

    user_info = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "last_interaction_at": now,
    }

    if user_id not in user_data:
        user_info["added_at"] = now
        user_data[user_id] = user_info
        logger.info(f"Пользователь {user.username or user.first_name} (ID: {user_id}) добавлен в базу.")
        save_user_data(user_data)
        return True
    else:
        updated = False
        if user_data[user_id].get('username') != user.username or \
           user_data[user_id].get('first_name') != user.first_name or \
           user_data[user_id].get('last_name') != user.last_name:
            updated = True
        user_data[user_id].update(user_info)
        if updated:
             logger.info(f"Данные пользователя {user.username or user.first_name} (ID: {user_id}) обновлены.")
        else:
             logger.debug(f"Обновлено время последнего взаимодействия для пользователя {user_id}")

        save_user_data(user_data)
        return False

async def is_user_subscribed(user_id: int, chat_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member_status = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        logger.debug(f"Статус пользователя {user_id} в чате {chat_id}: {member_status.status}")
        return member_status.status in ['member', 'administrator', 'creator']
    except BadRequest as e:
        logger.error(f"Ошибка BadRequest при проверке подписки {user_id} на {chat_id}: {e}")
        if "member list is inaccessible" in str(e).lower():
             logger.error(f"НЕ УДАЛОСЬ ПРОВЕРИТЬ ПОДПИСКУ: 'Member list is inaccessible'. Убедись, что бот является АДМИНИСТРАТОРОМ канала '{chat_id}' с правом добавления участников!")
        elif "user not found" in str(e).lower():
             logger.warning(f"Пользователь {user_id} не найден.")
             return False
        elif "chat not found" in str(e).lower():
             logger.error(f"Канал {chat_id} не найден. Проверь CHANNEL_ID.")
             return False
        elif "bot is not a member" in str(e).lower():
             logger.error(f"Бот не является участником канала {chat_id}. Добавьте бота в канал (и сделайте админом!).")
             return False
        return False
    except Forbidden as e:
        logger.error(f"Ошибка Forbidden: Бот не имеет прав на просмотр участников в {chat_id}. Сделайте его админом! {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке подписки {user_id} на {chat_id}: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    logger.info(f"Пользователь {user.username or user.first_name} (ID: {user_id}) запустил команду /start.")

    add_or_update_user(user)

    subscribed = await is_user_subscribed(user_id, CHANNEL_ID, context)

    if subscribed:
        logger.info(f"Пользователь {user_id} подписан. Отправляем драмкит.")
        await send_drumkit(user_id, context)
    else:
        logger.info(f"Пользователь {user_id} не подписан. Просим подписаться.")
        keyboard = [
            [InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
            [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n\n"
            f"Чтобы получить драмкит, пожалуйста, подпишись на наш канал: {CHANNEL_ID}\n\n"
            "После подписки нажми кнопку ниже 👇",
            reply_markup=reply_markup
        )

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    await query.answer()

    logger.info(f"Пользователь {user.username or user.first_name} (ID: {user_id}) нажал кнопку проверки подписки.")

    add_or_update_user(user)

    subscribed = await is_user_subscribed(user_id, CHANNEL_ID, context)

    if subscribed:
        logger.info(f"Пользователь {user_id} подтвердил подписку. Отправляем драмкит.")
        try:
            await query.edit_message_text(text="Отлично! Проверка прошла успешно. Отправляю твой драмкит...")
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                 logger.error(f"Ошибка при редактировании сообщения для {user_id} (успешная проверка): {e}")
        await send_drumkit(user_id, context)
    else:
        logger.info(f"Пользователь {user_id} нажал кнопку, но не подписан.")
        keyboard = [
            [InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
            [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(
                "Хм, я проверил, но пока не вижу тебя среди подписчиков канала.\n\n"
                f"Убедись, что ты подписался на {CHANNEL_ID} и попробуй нажать кнопку еще раз.",
                reply_markup=reply_markup
            )
        except BadRequest as e:
             if "message is not modified" not in str(e).lower():
                  logger.error(f"Ошибка при редактировании сообщения для {user_id} (неудачная проверка): {e}")

async def send_drumkit(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not os.path.exists(DRUMKIT_FILE_PATH):
             logger.error(f"Файл драмкита не найден по пути: {DRUMKIT_FILE_PATH}. Не могу отправить.")
             await context.bot.send_message(user_id, "Извини, возникла проблема с файлом драмкита. Администратор уведомлен!")
             if ADMIN_USER_ID:
                 try:
                     await context.bot.send_message(ADMIN_USER_ID, f"‼️ ОШИБКА: Не найден файл драмкита {DRUMKIT_FILE_PATH} при попытке отправки пользователю {user_id}!")
                 except Exception as admin_e:
                     logger.error(f"Не удалось уведомить админа об отсутствии файла: {admin_e}")
             return

        with open(DRUMKIT_FILE_PATH, 'rb') as drumkit_file:
            logger.info(f"Отправка файла {DRUMKIT_FILE_PATH} пользователю {user_id}")
            await context.bot.send_document(
                chat_id=user_id,
                document=drumkit_file,
                caption=MESSAGE_TEXT,
                parse_mode=ParseMode.HTML
            )
        logger.info(f"Драмкит успешно отправлен пользователю {user_id}.")

    except Forbidden:
        logger.warning(f"Пользователь {user_id} заблокировал бота. Не удалось отправить драмкит.")
    except Exception as e:
        logger.error(f"Ошибка при отправке драмкита пользователю {user_id}: {e}")
        try:
            await context.bot.send_message(user_id, "Извини, произошла ошибка при отправке файла.")
        except Forbidden:
             logger.warning(f"Пользователь {user_id} заблокировал бота (повторная проверка при ошибке).")
        except Exception as send_err:
             logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {send_err}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        logger.warning(f"Попытка использования /broadcast пользователем {user.id} ({user.username or user.first_name}), не являющимся админом.")
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    if not context.args:
        await update.message.reply_text(
            "Пожалуйста, укажи текст для рассылки после команды.\n"
            "Пример: `/broadcast Привет всем! Скоро новый кит!`\n"
            "Можно использовать базовое HTML форматирование: <b>жирный</b>, <i>курсив</i>, <a href='...'>ссылка</a>.",
            parse_mode=ParseMode.MARKDOWN
            )
        return

    message_text = update.message.text.split(' ', 1)[1]

    user_data = load_user_data()
    if not user_data:
        await update.message.reply_text("В базе нет пользователей для рассылки.")
        return

    user_ids = list(user_data.keys())

    logger.info(f"Админ {user.id} начинает рассылку сообщения для {len(user_ids)} пользователей.")
    await update.message.reply_text(f"Начинаю рассылку для {len(user_ids)} пользователей...\n"
                                     f"Текст:\n{message_text[:100]}{'...' if len(message_text)>100 else ''}")

    success_count = 0
    fail_count = 0
    blocked_count = 0
    active_users_after_broadcast = user_data.copy()

    for user_id in user_ids:
        user_info = user_data.get(user_id, {})
        username = user_info.get('username', 'N/A')
        first_name = user_info.get('first_name', 'N/A')

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            success_count += 1
            logger.debug(f"Сообщение успешно отправлено пользователю {user_id} ({username})")
        except Forbidden:
            logger.warning(f"Пользователь {user_id} ({username}) заблокировал бота. Не удалось отправить сообщение.")
            fail_count += 1
            blocked_count += 1
            if user_id in active_users_after_broadcast:
                 del active_users_after_broadcast[user_id]
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id} ({username}): {e}")
            fail_count += 1

    logger.info(f"Рассылка завершена. Успешно: {success_count}, Неудачно: {fail_count} (Заблокировали: {blocked_count})")

    save_user_data(active_users_after_broadcast)
    logger.info(f"Обновлена база данных, удалено {blocked_count} заблокировавших пользователей.")

    await update.message.reply_text(
        f"✅ Рассылка завершена!\n"
        f"Успешно отправлено: {success_count}\n"
        f"Не удалось отправить: {fail_count}\n"
        f"   (Из них заблокировали бота: {blocked_count} - они удалены из базы)"
    )


def main() -> None:
    if not os.path.exists(DRUMKIT_FILE_PATH):
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Файл драмкита '{DRUMKIT_FILE_PATH}' не найден! Бот не сможет отправлять его.")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern='^check_subscription$'))
    application.add_handler(CommandHandler("broadcast", broadcast))

    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == '__main__':
    main()
