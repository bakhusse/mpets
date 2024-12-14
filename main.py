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
import time

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

# Проверка на возможность действия (кормить, играть, выставка)
def check_action_links(page_html):
    actions = {
        "food": "https://mpets.mobi/?action=food",
        "play": "https://mpets.mobi/?action=play",
        "show": "https://mpets.mobi/show"
    }
    
    action_found = {}
    
    # Проверка на наличие картинок с гиперссылками
    for action, link in actions.items():
        image_pattern = r'<a href="{}"><img'.format(link)
        match = re.search(image_pattern, page_html)
        action_found[action] = bool(match)
    
    return action_found

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
    
    # Если cookies пустые, возвращаем ошибку
    if not cookies_dict:
        logging.error("Ошибка: cookies пустые или некорректные.")
        return None
    
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

    # Перед авторизацией проверяем возможность действий (кормление, игра, выставка)
    action_found = check_action_links(response.text)
    logging.info(f"Доступные действия: {action_found}")
    
    if action_found["food"]:
        logging.info("Можно покормить питомца, переходим по ссылке.")
        session.get("https://mpets.mobi/?action=food")  # Переходим по ссылке кормления 6 раз
        for _ in range(5):
            session.get("https://mpets.mobi/?action=food")

    if action_found["play"]:
        logging.info("Можно поиграть с питомцем, переходим по ссылке.")
        session.get("https://mpets.mobi/?action=play")

    if action_found["show"]:
        logging.info("Можно посетить выставку, переходим по ссылке.")
        session.get("https://mpets.mobi/show")
    
    return session, response

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

# Функция для извлечения времени ожидания из текста
def extract_wait_time(text):
    # Ищем строку вида "Проснется через: 18м 55с"
    match = re.search(r"Проснется через: (\d+)м (\d+)с", text)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        total_seconds = minutes * 60 + seconds
        logging.info(f"Время ожидания: {total_seconds} секунд.")
        return total_seconds
    return None

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
    session, response = start_session_with_cookies(update, context, cookies_str)
    
    if session is None:
        await update.message.reply_text("Не удалось авторизоваться с предоставленными cookies. Пожалуйста, проверьте их и попробуйте снова.")
        return COOKIES

    # Если авторизация прошла успешно, обновляем страницу
    logging.info("Авторизация прошла успешно, выполняем обновление страницы.")
    response = session.get("https://mpets.mobi/welcome")  # Выполняем повторный запрос для обновления страницы

    # Проверяем, что авторизация успешна
    if response.status_code == 200:
        await update.message.reply_text("Авторизация успешна!")

        # Проверяем наличие изображения на обновленной странице
        if check_image_on_page(response.text):
            await update.message.reply_text("Изображение найдено на странице, все в порядке!")
        
        # Пытаемся извлечь время ожидания
        wait_time = extract_wait_time(response.text)
        if wait_time:
            # Устанавливаем таймер на извлеченное время
            minutes, seconds = divmod(wait_time, 60)
            await update.message.reply_text(f"Таймер установлен на {minutes}м {seconds}с.")

            # Ожидаем указанное время
            await asyncio.sleep(wait_time)

            # Отправляем сообщение о завершении таймера
            await update.message.reply_text("Проснулся! Таймер завершен.")
        else:
            await update.message.reply_text("Не удалось найти время ожидания на странице.")
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
