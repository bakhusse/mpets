import asyncio
import requests
import json
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
import logging
import colorlog
import os
import re

# Для работы с циклом событий внутри Google Colab
nest_asyncio.apply()

# Состояния для ConversationHandler
START, COOKIES = range(2)

# Ваш токен Telegram-бота
TOKEN = '7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4'

# Папка для сохранения капчи
CAPTCHA_FOLDER = 'captcha_images'
if not os.path.exists(CAPTCHA_FOLDER):
    os.makedirs(CAPTCHA_FOLDER)

# Настройка цветного логирования
log_formatter = colorlog.ColoredFormatter(
    '%(log_color)s[%(asctime)s] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'blue',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logging.getLogger().addHandler(console_handler)
logging.getLogger().setLevel(logging.DEBUG)

# Функция для создания новой сессии
def create_new_session():
    session = requests.Session()
    logging.info("Создание новой сессии.")
    return session

# Преобразование cookies в нужный формат
def parse_cookies(cookies_data):
    cookies_dict = {}
    
    # Если переданы данные в формате JSON
    if isinstance(cookies_data, list):
        for cookie in cookies_data:
            name = cookie.get("name")
            value = cookie.get("value")
            if name and value:
                cookies_dict[name] = value
    
    # Если переданы данные в строковом формате
    elif isinstance(cookies_data, str):
        for cookie in cookies_data.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                cookies_dict[key] = value
    
    return cookies_dict

# Эмуляция сессии через cookies
def start_session_with_cookies(update, context, cookies_str):
    session = create_new_session()
    context.user_data['session'] = session  # Сохраняем сессию в контексте пользователя

    try:
        # Пробуем распарсить cookies как JSON
        cookies_data = json.loads(cookies_str)
        cookies_dict = parse_cookies(cookies_data)
    except json.JSONDecodeError:
        # Если не JSON, пробуем строку cookies
        cookies_dict = parse_cookies(cookies_str)
    
    # Добавляем cookies в сессию
    session.cookies.update(cookies_dict)
    logging.info(f"Сессия с cookies: {session.cookies.get_dict()}")

    # Примерный URL для проверки авторизации
    welcome_url = "https://mpets.mobi/welcome"
    logging.info(f"Запрос на страницу {welcome_url}")
    response = session.get(welcome_url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу welcome. Статус: {response.status_code}")
        return None
    
    logging.info(f"Сессия сохранена, cookies: {session.cookies.get_dict()}")

    return session

# Функция для проверки наличия изображения на странице
def check_image_on_page(page_html):
    # Ищем элемент <img class="price_img" src="/view/image/icons/coin.png" alt=""/>
    image_pattern = r'<img class="price_img" src="/view/image/icons/coin.png" alt="">'
    match = re.search(image_pattern, page_html)

    if match:
        logging.info("Изображение найдено на странице.")
        return True
    else:
        logging.error("Изображение не найдено на странице.")
        return False

# Обработка команды /start
async def start(update: Update, context: CallbackContext) -> int:
    logging.info("Начало процесса авторизации через cookies.")
    await update.message.reply_text("Привет! Отправь свои cookies для авторизации в одном из следующих форматов:\n"
                                    "1. JSON-массив объектов cookies\n"
                                    "2. Строка cookies в формате: cookie1=value1; cookie2=value2")
    return COOKIES

# Обработка получения cookies от пользователя
async def cookies(update: Update, context: CallbackContext) -> int:
    cookies_str = update.message.text.strip()
    
    logging.info(f"Пользователь отправил cookies: {cookies_str}")

    if not cookies_str:
        await update.message.reply_text("Ошибка: Пожалуйста, отправьте cookies в правильном формате.")
        return COOKIES

    # Создаем сессию с переданными cookies
    session = start_session_with_cookies(update, context, cookies_str)
    
    if session is None:
        await update.message.reply_text("Не удалось авторизоваться с предоставленными cookies. Попробуйте снова.")
        return COOKIES

    # Проверяем, что авторизация успешна
    welcome_url = "https://mpets.mobi/welcome"
    response = session.get(welcome_url)

    if response.status_code == 200:
        await update.message.reply_text("Авторизация успешна!")
        
        # Проверяем наличие изображения на странице
        if check_image_on_page(response.text):
            await update.message.reply_text("Изображение найдено на странице, все в порядке!")
        else:
            await update.message.reply_text("Изображение не найдено на странице.")
    else:
        await update.message.reply_text("Ошибка: Не удалось авторизоваться. Пожалуйста, проверьте cookies и попробуйте снова.")

    return START

# Главная функция
async def main():
    application = Application.builder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            COOKIES: [MessageHandler(filters.TEXT, cookies)],
            START: [MessageHandler(filters.TEXT, lambda update, context: update.message.reply_text("Добро пожаловать!"))],
        },
        fallbacks=[],
    )

    application.add_handler(conversation_handler)

    logging.info("Бот запущен.")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
