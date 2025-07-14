import os
import logging
import sqlite3
from contextlib import closing
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
    PicklePersistence  # Замена Persistence
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

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        "Отправь сюда свои предложения, вопросы или сообщения. "
        "Я анонимно передам их администратору.\n\n"
        "Можешь прикреплять текст, фото, видео, документы и другие файлы."
    )

async def handle_message(update: Update, context: CallbackContext):
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
            sent_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{user_info}\n\n📩 Сообщение:\n{message.text}",
                reply_markup=keyboard
            )
        elif message.photo:
            content_type = "photo"
            sent_msg = await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"{user_info}\n\n📩 Подпись к фото:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.video:
            content_type = "video"
            sent_msg = await context.bot.send_video(
                chat_id=ADMIN_ID,
                video=message.video.file_id,
                caption=f"{user_info}\n\n📩 Подпись к видео:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.document:
            content_type = "document"
            sent_msg = await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=message.document.file_id,
                caption=f"{user_info}\n\n📩 Подпись к документу:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.audio:
            content_type = "audio"
            sent_msg = await context.bot.send_audio(
                chat_id=ADMIN_ID,
                audio=message.audio.file_id,
                caption=f"{user_info}\n\n📩 Подпись к аудио:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        elif message.voice:
            content_type = "voice"
            sent_msg = await context.bot.send_voice(
                chat_id=ADMIN_ID,
                voice=message.voice.file_id,
                caption=f"{user_info}\n\n📩 Голосовое сообщение",
                reply_markup=keyboard
            )
        elif message.sticker:
            content_type = "sticker"
            await context.bot.send_sticker(chat_id=ADMIN_ID, sticker=message.sticker.file_id)
            sent_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{user_info}\n\n📩 Пользователь отправил стикер",
                reply_markup=keyboard
            )
        elif message.video_note:
            content_type = "video_note"
            await context.bot.send_video_note(chat_id=ADMIN_ID, video_note=message.video_note.file_id)
            sent_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{user_info}\n\n📩 Пользователь отправил видео-заметку",
                reply_markup=keyboard
            )
        elif message.animation:
            content_type = "animation"
            sent_msg = await context.bot.send_animation(
                chat_id=ADMIN_ID,
                animation=message.animation.file_id,
                caption=f"{user_info}\n\n📩 Подпись к GIF:\n{message.caption or '-'}",
                reply_markup=keyboard
            )
        else:
            content_type = "other"
            sent_msg = await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=message.effective_attachment.file_id,
                caption=f"{user_info}\n\n📩 Сообщение с файлом\nТип: {message.effective_attachment.mime_type}",
                reply_markup=keyboard
            )
        
        # Сохраняем связь между сообщениями в БД
        save_message(user.id, message.message_id, sent_msg.message_id)
        logger.info(f"Сообщение от {user.id} сохранено. Тип: {content_type}")
        
        await update.message.reply_text("✅ Сообщение доставлено администратору!")
        
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при отправке сообщения.")

async def reply_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    # Извлекаем ID оригинального сообщения
    original_message_id = int(query.data.split('_')[1])
    
    # Сохраняем связь для ответа
    context.user_data['replying_to'] = original_message_id
    await query.edit_message_text(
        text=query.message.text + "\n\n🟢 ОТВЕТ АКТИВИРОВАН! Введите ваш ответ:",
        reply_markup=None
    )

async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    
    reply_data = context.user_data.get('replying_to')
    if not reply_data:
        return
    
    # Находим пользователя для ответа
    user_data = get_user_data(reply_data)
    if not user_data:
        await update.message.reply_text("⚠️ Ошибка: пользователь не найден.")
        return
    
    user_id, admin_msg_id = user_data
    message = update.effective_message
    
    try:
        # Обработка ответов разных типов
        content_type = None
        if message.text:
            content_type = "text"
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📨 Ответ от администратора:\n\n{message.text}"
            )
        elif message.photo:
            content_type = "photo"
            await context.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.video:
            content_type = "video"
            await context.bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.document:
            content_type = "document"
            await context.bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.audio:
            content_type = "audio"
            await context.bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        elif message.voice:
            content_type = "voice"
            await context.bot.send_voice(
                chat_id=user_id,
                voice=message.voice.file_id,
                caption=f"📨 Ответ от администратора:"
            )
        elif message.sticker:
            content_type = "sticker"
            await context.bot.send_sticker(
                chat_id=user_id,
                sticker=message.sticker.file_id
            )
        elif message.video_note:
            content_type = "video_note"
            await context.bot.send_video_note(
                chat_id=user_id,
                video_note=message.video_note.file_id
            )
        elif message.animation:
            content_type = "animation"
            await context.bot.send_animation(
                chat_id=user_id,
                animation=message.animation.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        else:
            content_type = "other"
            await context.bot.send_document(
                chat_id=user_id,
                document=message.effective_attachment.file_id,
                caption=f"📨 Ответ от администратора:\n\n{message.caption or ''}"
            )
        
        # Удаляем временные данные
        if 'replying_to' in context.user_data:
            del context.user_data['replying_to']
        delete_pending_reply(user_id)
        
        try:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=admin_msg_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение: {e}")
        
        logger.info(f"Ответ отправлен пользователю {user_id}. Тип: {content_type}")
        await update.message.reply_text("✅ Ответ успешно отправлен пользователю!")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа: {e}")
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

def main():
    # Инициализация базы данных
    init_db()
    
    # Создание Application с PicklePersistence
    persistence = PicklePersistence(filepath='bot_persistence.pickle')
    application = Application.builder().token(TOKEN).persistence(persistence).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL |
        filters.AUDIO | filters.VOICE | filters.Sticker.ALL | filters.VIDEO_NOTE |
        filters.ANIMATION | filters.ATTACHMENT,
        handle_message
    ))
    application.add_handler(CallbackQueryHandler(reply_callback, pattern=r"^reply_\d+$"))
    application.add_handler(MessageHandler(filters.Chat(ADMIN_ID) & ~filters.COMMAND, handle_admin_reply))

    # Настройка для Render
    if RENDER_EXTERNAL_HOSTNAME:
        # Настройка вебхука
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"https://{RENDER_EXTERNAL_HOSTNAME}/{TOKEN}"
        )
        logger.info("Бот запущен через вебхук")
    else:
        # Локальный запуск
        application.run_polling()
        logger.info("Бот запущен локально с polling")

if __name__ == "__main__":
    main()
