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
from bs4 import BeautifulSoup

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
    
    if isinstance(cookies_data, list):
        for cookie in cookies_data:
            name = cookie.get("name")
            value = cookie.get("value")
            if name and value:
                cookies_dict[name] = value
    elif isinstance(cookies_data, str):
        for cookie in cookies_data.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                cookies_dict[key] = value
    
    return cookies_dict

# Проверка сна
def check_sleep(session):
    url = "https://mpets.mobi/"
    logging.info(f"Проверка времени сна по ссылке: {url}")
    response = session.get(url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу сна. Статус: {response.status_code}")
        return None
    
    match = re.search(r"Проснется через (\d+)ч (\d+)м", response.text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_seconds = (hours * 60 * 60) + (minutes * 60)
        logging.info(f"Питомец проснется через {hours}ч {minutes}м.")
        return total_seconds
    
    return None

# Проверка поляны
def check_glade(session):
    url = "https://mpets.mobi/glade"
    logging.info(f"Проверка поляны по ссылке: {url}")
    response = session.get(url)

    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу поляны. Статус: {response.status_code}")
        return None
    
    match = re.search(r"5 попыток закончились, возвращайтесь через (\d+) час (\d+) минут", response.text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_seconds = (hours * 60 * 60) + (minutes * 60)
        logging.info(f"Попытки закончились, нужно подождать {hours}ч {minutes}м.")
        return total_seconds
    
    return None

# Проверка прогулки
def check_travel(session):
    url = "https://mpets.mobi/travel"
    logging.info(f"Проверка прогулки по ссылке: {url}")
    response = session.get(url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу прогулки. Статус: {response.status_code}")
        return None
    
    match = re.search(r"До конца прогулки осталось (\d+)ч (\d+)м", response.text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_seconds = (hours * 60 * 60) + (minutes * 60)
        logging.info(f"До конца прогулки осталось {hours}ч {minutes}м.")
        return total_seconds
    
    return None

# Проверка на семена на поляне
def find_seeds(session):
    url = "https://mpets.mobi/glade"
    logging.info(f"Попытка найти семена по ссылке: {url}")
    response = session.get(url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу поляны для поиска семян. Статус: {response.status_code}")
        return None
    
    # Пытаемся найти семена 6 раз
    for _ in range(6):
        session.get(url)
        logging.info("Попытка найти семена выполнена.")
    
    return True

# Отправка питомца гулять
def send_pet_to_travel(session):
    url = "https://mpets.mobi/travel"
    logging.info(f"Отправляем питомца гулять по ссылке: {url}")
    response = session.get(url)
    if response.status_code == 200:
        logging.info("Питомец отправлен гулять.")
        return True
    logging.error(f"Не удалось отправить питомца гулять. Статус: {response.status_code}")
    return False

# Эмуляция сессии через cookies
def start_session_with_cookies(update, context, cookies_str):
    session = create_new_session()
    context.user_data['session'] = session  # Сохраняем сессию в контексте пользователя

    try:
        cookies_data = json.loads(cookies_str)
        cookies_dict = parse_cookies(cookies_data)
    except json.JSONDecodeError:
        cookies_dict = parse_cookies(cookies_str)
    
    if not cookies_dict:
        logging.error("Ошибка: cookies пустые или некорректные.")
        return None
    
    session.cookies.update(cookies_dict)
    logging.info(f"Сессия с cookies: {session.cookies.get_dict()}")

    return session

# Отправка уведомлений в Telegram
async def send_telegram_notification(update: Update, message: str):
    await update.message.reply_text(message)

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

    session = start_session_with_cookies(update, context, cookies_str)
    
    if session is None:
        await update.message.reply_text("Не удалось авторизоваться с предоставленными cookies. Пожалуйста, проверьте их и попробуйте снова.")
        return COOKIES

    await update.message.reply_text("Авторизация успешна! Теперь выполняем проверки.")

    # 1. Проверка сна
    sleep_time = check_sleep(session)
    
    if sleep_time:
        # Установим таймер
        await send_telegram_notification(update, f"Питомец спит. Проснется через {sleep_time // 3600}ч {(sleep_time % 3600) // 60}м.")
        await asyncio.sleep(sleep_time)
        await send_telegram_notification(update, "Питомец проснулся!")
    else:
        # Если питомец не спит, проверяем еду, игру и выставку
        logging.info("Питомец не спит, проверяем еду, игру и выставку.")
        # Эта часть кода зависит от логики вашего бота для проверки еды, игры и выставки.
        # Здесь можно добавить соответствующую логику для того, чтобы выполнить проверку этих действий.

    # 2. Проверка поляны
    glade_time = check_glade(session)
    
    if glade_time:
        # Установим таймер для поляны
        await send_telegram_notification(update, f"Попытки закончились, возвращайтесь через {glade_time // 3600}ч {(glade_time % 3600) // 60}м.")
        await asyncio.sleep(glade_time)
        await send_telegram_notification(update, "Теперь можете вернуться на поляну!")
    else:
        # Если поле не закрыто, пробуем найти семена
        find_seeds(session)
        await send_telegram_notification(update, "Попытки найти семена выполнены.")

    # 3. Проверка прогулки
    travel_time = check_travel(session)
    
    if travel_time:
        # Установим таймер для прогулки
        await send_telegram_notification(update, f"До конца прогулки осталось {travel_time // 3600}ч {(travel_time % 3600) // 60}м.")
        await asyncio.sleep(travel_time)
        await send_telegram_notification(update, "Прогулка завершена!")
    else:
        # Если прогулка не идет, отправляем питомца гулять
        send_pet_to_travel(session)
        await send_telegram_notification(update, "Питомец отправлен гулять.")

    return ConversationHandler.END

# Основная функция для запуска бота
def main():
    application = Application.builder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookies)],
        },
        fallbacks=[],
    )

    application.add_handler(conversation_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
