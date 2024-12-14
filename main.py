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

# Функция для извлечения времени сна питомца
def extract_sleep_time(page_html):
    """
    Функция для извлечения времени сна питомца с HTML страницы.
    Если питомец спит, возвращает время в секундах.
    Если питомец не спит, возвращает None.
    """
    match = re.search(r"Ваш питомец спит и проснется через (\d+)ч (\d+)м", page_html)
    
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return (hours * 3600) + (minutes * 60)
    
    return None

# Проверка на возможность действия (кормить, играть)
def check_action_links(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')

    food_link = soup.find('a', href=re.compile(r'/?action=food&rand=\d+'))
    play_link = soup.find('a', href=re.compile(r'/?action=play&rand=\d+'))

    action_found = {
        "food": bool(food_link),
        "play": bool(play_link)
    }
    
    return action_found, food_link, play_link

# Проверка поляны
def check_glade(session):
    url = "https://mpets.mobi/glade"
    logging.info(f"Проверка поляны по ссылке: {url}")
    response = session.get(url)

    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу поляны. Статус: {response.status_code}")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    # Проверка на наличие шанса найти семена
    if "Шанс найти семена" in response.text:
        logging.info("Шанс найти семена на поляне!")
        return True
    
    # Если попытки кончились, извлекаем время, когда можно будет снова попытаться
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
    
    # Проверка, гуляет ли питомец
    if "Ваш питомец гуляет" in response.text:
        match = re.search(r"До конца прогулки осталось (\d+)ч (\d+)м", response.text)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            total_seconds = (hours * 60 * 60) + (minutes * 60)
            logging.info(f"Питомец гуляет. Ожидайте {hours}ч {minutes}м.")
            return total_seconds
        else:
            logging.info("Текст о времени прогулки не найден.")
    else:
        logging.info("Питомец не гуляет.")
    
    return None

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

    welcome_url = "https://mpets.mobi/welcome"
    logging.info(f"Запрос на страницу {welcome_url}")
    response = session.get(welcome_url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу welcome. Статус: {response.status_code}")
        return None
    
    logging.info(f"Сессия сохранена, cookies: {session.cookies.get_dict()}")

    return session, response

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

    session, response = start_session_with_cookies(update, context, cookies_str)
    
    if session is None:
        await update.message.reply_text("Не удалось авторизоваться с предоставленными cookies. Пожалуйста, проверьте их и попробуйте снова.")
        return COOKIES

    await update.message.reply_text("Авторизация успешна! Теперь выполняем проверки.")

    # Проверка состояния сна питомца
    logging.info("Проверка состояния сна питомца.")
    sleep_time = extract_sleep_time(response.text)
    
    if sleep_time:
        await update.message.reply_text(f"Питомец спит. Проснется через {sleep_time // 3600}ч {(sleep_time % 3600) // 60}м.")
        await asyncio.sleep(sleep_time)
        await update.message.reply_text("Питомец проснулся!")
    else:
        # Питомец не спит, выполняем другие действия
        logging.info("Питомец не спит. Проверяем возможность кормления и игры.")
        action_found, food_link, play_link = check_action_links(response.text)
        
        # Используем полный URL для перехода
        base_url = "https://mpets.mobi"
        
        if action_found["food"]:
            logging.info("Переход по ссылке кормления.")
            for _ in range(6):
                food_url = base_url + food_link["href"]
                session.get(food_url)
            await update.message.reply_text("Питомец поел.")

        if action_found["play"]:
            logging.info("Переход по ссылке игры.")
            for _ in range(6):
                play_url = base_url + play_link["href"]
                session.get(play_url)
            await update.message.reply_text("Питомец поиграл.")

    # Проверка поляны
    glade_check = check_glade(session)
    if glade_check is True:
        logging.info("Переход по ссылке для поиска семян на поляне.")
        for _ in range(6):  # Переход по ссылке поиска семян 6 раз
            session.get(f"{base_url}/glade_dig")
        await update.message.reply_text("Вы нашли семена на поляне!")
    elif isinstance(glade_check, int):
        await update.message.reply_text(f"Невозможно найти семена на поляне. Ожидайте {glade_check // 3600}ч {(glade_check % 3600) // 60}м.")
        await asyncio.sleep(glade_check)
        await update.message.reply_text("Время ожидания прошло. Ищем семена на поляне.")
        for _ in range(6):  # Переход по ссылке поиска семян 6 раз
            session.get(f"{base_url}/glade_dig")
        await update.message.reply_text("Вы нашли семена на поляне!")

    # Проверка прогулки
    logging.info("Проверка прогулки.")
    travel_time = check_travel(session)
    if travel_time:
        await update.message.reply_text(f"Питомец гуляет. Ожидайте {travel_time // 3600}ч {(travel_time % 3600) // 60}м.")
        await asyncio.sleep(travel_time)
    else:
        logging.info("Питомец не гуляет, отправляем его на прогулку.")
        for i in range(10, 0, -1):
            session.get(f"{base_url}/go_travel?id={i}")
        await update.message.reply_text("Питомец сходил на прогулку.")

    return ConversationHandler.END

# Основная функция для запуска бота
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookies)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
