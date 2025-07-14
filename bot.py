import os
import logging
import sqlite3
from contextlib import closing
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    Persistence
)

# Конфигурация
TOKEN = os.environ.get('TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
PORT = int(os.environ.get('PORT', 5000))
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_db():
    with closing(sqlite3.connect('data.db')) as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            user_message_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            admin_message_id INTEGER NOT NULL
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS pending_replies (
            user_id INTEGER PRIMARY KEY,
            admin_message_id INTEGER NOT NULL
        )
        ''')
        conn.commit()

# Функции для работы с базой данных
def save_message(user_id, user_message_id, admin_message_id):
    with closing(sqlite3.connect('data.db')) as conn:
        conn.execute("INSERT INTO messages VALUES (?, ?, ?)", 
                    (user_message_id, user_id, admin_message_id))
        conn.execute("INSERT OR REPLACE INTO pending_replies VALUES (?, ?)", 
                    (user_id, admin_message_id))
        conn.commit()

def get_user_data(user_message_id):
    with closing(sqlite3.connect('data.db')) as conn:
        cur = conn.execute("SELECT user_id, admin_message_id FROM messages WHERE user_message_id = ?", 
                          (user_message_id,))
        return cur.fetchone()

def delete_pending_reply(user_id):
    with closing(sqlite3.connect('data.db')) as conn:
        conn.execute("DELETE FROM pending_replies WHERE user_id = ?", (user_id,))
        conn.commit()

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        "Отправь сюда свои предложения, вопросы или сообщения. "
        "Я анонимно передам их администратору.\n\n"
        "Можешь прикреплять текст, фото, видео, документы и другие файлы."
    )

def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.effective_message
    
    # Формируем информацию о пользователе
    user_info = (
        f"👤 Отправитель:\n"
        f"ID: {user.id}\n"
        f"Имя: {user.first_name or '-'}\n"
        f"Фамилия: {user.last_name or '-'}\n"
        f"Юзернейм: @{user.username if user.username else 'отсутствует'}\n"
        f"Язык: {user.language_code or '-'}"
    )
    
    # Формируем клавиатуру с кнопкой "Ответить"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{message.message_id}")
    ]])
    
    try:
        # Обработка разных типов контента
        content_type = None
        if message.text:
            content_type = "text"
            sent_msg = context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{user_info}\n\n📩 Сообщение:\n{message.text}",
                reply_markup=keyboard
            )
        elif message.photo:
            content_type = "photo"
            sent_msg = context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"{user_info}\n\n📩 Подпись к фото:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.video:
            content_type = "video"
            sent_msg = context.bot.send_video(
                chat_id=ADMIN_ID,
                video=message.video.file_id,
                caption=f"{user_info}\n\n📩 Подпись к видео:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.document:
            content_type = "document"
            sent_msg = context.bot.send_document(
                chat_id=ADMIN_ID,
                document=message.document.file_id,
                caption=f"{user_info}\n\n📩 Подпись к документу:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.audio:
            content_type = "audio"
            sent_msg = context.bot.send_audio(
                chat_id=ADMIN_ID,
                audio=message.audio.file_id,
                caption=f"{user_info}\n\n📩 Подпись к аудио:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.voice:
            content_type = "voice"
            sent_msg = context.bot.send_voice(
                chat_id=ADMIN_ID,
                voice=message.voice.file_id,
                caption=f"{user_info}\n\n📩 Голосовое сообщение",
                reply_markup=keyboard
            )
        elif message.sticker:
            content_type = "sticker"
            context.bot.send_sticker(chat_id=ADMIN_ID, sticker=message.sticker.file_id)
            sent_msg = context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{user_info}\n\n📩 Пользователь отправил стикер",
                reply_markup=keyboard
            )
        elif message.video_note:
            content_type = "video_note"
            context.bot.send_video_note(chat_id=ADMIN_ID, video_note=message.video_note.file_id)
            sent_msg = context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{user_info}\n\n📩 Пользователь отправил видео-заметку",
                reply_markup=keyboard
            )
        elif message.animation:
            content_type = "animation"
            sent_msg = context.bot.send_animation(
                chat_id=ADMIN_ID,
                animation=message.animation.file_id,
                caption=f"{user_info}\n\n📩 Подпись к GIF:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        else:
            content_type = "other"
            sent_msg = context.bot.send_document(
                chat_id=ADMIN_ID,
                document=message.effective_attachment.file_id,
                caption=f"{user_info}\n\n📩 Сообщение с файлом\nТип: {message.effective_attachment.mime_type}",
                reply_markup=keyboard
            )
        
        # Сохраняем связь между сообщениями в БД
        save_message(user.id, message.message_id, sent_msg.message_id)
        logger.info(f"Сообщение от {user.id} сохранено. Тип: {content_type}")
        
        update.message.reply_text("✅ Сообщение доставлено администратору!")
        
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        update.message.reply_text("⚠️ Произошла ошибка при отправке сообщения.")

def reply_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    # Извлекаем ID оригинального сообщения
    original_message_id = int(query.data.split('_')[1])
    
    # Сохраняем связь для ответа
    context.user_data['replying_to'] = original_message_id
    query.edit_message_text(
        query.message.text + "\n\n🟢 ОТВЕТ АКТИВИРОВАН! Введите ваш ответ:",
        reply_markup=None
    )

def handle_admin_reply(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    
    reply_data = context.user_data.get('replying_to')
    if not reply_data:
        return
    
    # Находим пользователя для ответа
    user_data = get_user_data(reply_data)
    if not user_data:
        update.message.reply_text("⚠️ Ошибка: пользователь не найден.")
        return
    
    user_id, admin_msg_id = user_data
    message = update.effective_message
    
    try:
        # Обработка ответов разных типов
        content_type = None
        if message.text:
            content_type = "text"
            context.bot.send_message(
                chat_id=user_id,
                text=f"📨 Ответ от администратора:\n\n{message.text}"
            )
        elif message.photo:
            content_type = "photo"
            context.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.video:
            content_type = "video"
            context.bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.document:
            content_type = "document"
            context.bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.audio:
            content_type = "audio"
            context.bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.voice:
            content_type = "voice"
            context.bot.send_voice(
                chat_id=user_id,
                voice=message.voice.file_id,
                caption=f"📨 Ответ от администратора:"
            )
        elif message.sticker:
            content_type = "sticker"
            context.bot.send_sticker(
                chat_id=user_id,
                sticker=message.sticker.file_id
            )
        elif message.video_note:
            content_type = "video_note"
            context.bot.send_video_note(
                chat_id=user_id,
                video_note=message.video_note.file_id
            )
        elif message.animation:
            content_type = "animation"
            context.bot.send_animation(
                chat_id=user_id,
                animation=message.animation.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        else:
            content_type = "other"
            context.bot.send_document(
                chat_id=user_id,
                document=message.effective_attachment.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        
        # Удаляем временные данные
        del context.user_data['replying_to']
        delete_pending_reply(user_id)
        
        try:
            context.bot.delete_message(chat_id=ADMIN_ID, message_id=admin_msg_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение: {e}")
        
        logger.info(f"Ответ отправлен пользователю {user_id}. Тип: {content_type}")
        update.message.reply_text("✅ Ответ успешно отправлен пользователю!")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа: {e}")
        update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

def main():
    # Инициализация базы данных
    init_db()
    
    # Создание объекта Updater
    persistence = Persistence(filename='bot_persistence')
    updater = Updater(TOKEN, persistence=persistence)
    dp = updater.dispatcher

    # Регистрация обработчиков
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(
        Filters.text | Filters.photo | Filters.video | Filters.document |
        Filters.audio | Filters.voice | Filters.sticker | Filters.video_note |
        Filters.animation | Filters.attachment,
        handle_message
    ))
    dp.add_handler(CallbackQueryHandler(reply_callback, pattern=r"^reply_\d+$"))
    dp.add_handler(MessageHandler(Filters.chat(ADMIN_ID) & ~Filters.command, handle_admin_reply))

    # Настройка вебхука для Render
    if RENDER_EXTERNAL_HOSTNAME:
        # Используем вебхук на Render
        updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://{RENDER_EXTERNAL_HOSTNAME}/{TOKEN}"
        )
        logger.info("Бот запущен через вебхук")
    else:
        # Локальный запуск с polling
        updater.start_polling()
        logger.info("Бот запущен локально с polling")

    updater.idle()

if __name__ == "__main__":
    main()