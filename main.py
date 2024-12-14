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
import random
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

# Проверка на возможность действия (кормить, играть)
def check_action_links(page_html):
    # Используем BeautifulSoup для парсинга HTML
    soup = BeautifulSoup(page_html, 'html.parser')

    # Ищем ссылки для кормления и игры
    food_link = soup.find('a', href=re.compile(r'/?action=food&rand=\d+'))
    play_link = soup.find('a', href=re.compile(r'/?action=play&rand=\d+'))

    action_found = {
        "food": bool(food_link),
        "play": bool(play_link)
    }
    
    # Логируем результаты
    if not action_found["food"]:
        logging.warning("Не найдено действие для кормления.")
    if not action_found["play"]:
        logging.warning("Не найдено действие для игры.")
    
    return action_found, food_link, play_link

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

    return session, response

# Функция для извлечения времени сна питомца
def extract_sleep_time(page_html):
    # Ищем шаблон "Питомец устал и уснул. Проснется через: 1ч 52м"
    match = re.search(r"Питомец устал и уснул\. Проснется через: (\d+)ч (\d+)м", page_html)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_seconds = (hours * 60 * 60) + (minutes * 60)
        return total_seconds
    return None

# Проверка на завершение прогулки
def check_travel_complete(page_html):
    # Ищем текст "Прогулка завершена!"
    if "Прогулка завершена!" in page_html:
        return True
    return False

# Проверка наличия семян на поляне
def check_seeds_found(page_html):
    if "Шанс найти семена" in page_html:
        return True
    return False

# Проверка на завершение попыток на поляне и извлечение времени
def extract_glade_time(page_html):
    # Ищем текст о завершении попыток
    match = re.search(r"5 попыток закончились, возвращайтесь через (\d+) час (\d+) минут", page_html)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        total_seconds = (hours * 60 * 60) + (minutes * 60)
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

    # Проверяем, спит ли питомец
    logging.info("Проверка состояния сна питомца.")
    sleep_time = extract_sleep_time(response.text)
    
    if sleep_time:
        logging.info(f"Питомец спит, проснется через {sleep_time // 3600}ч {(sleep_time % 3600) // 60}м.")
        await update.message.reply_text(f"Питомец спит. Проснется через {sleep_time // 3600}ч {(sleep_time % 3600) // 60}м.")
        
        # Устанавливаем таймер
        await asyncio.sleep(sleep_time)
        await update.message.reply_text("Питомец проснулся!")

    # После того как питомец просыпается, выполняем действия с едой, игрой и выставкой
    action_found, food_link, play_link = check_action_links(response.text)
    
    if action_found["food"]:
        logging.info("Можно покормить питомца, переходим по ссылке.")
        # Генерируем случайное значение для rand и переходим по ссылке
        rand_food = random.randint(1000, 9999)
        session.get(f"https://mpets.mobi/?action=food&rand={rand_food}")  # Переходим по ссылке кормления 6 раз
        for _ in range(5):
            rand_food = random.randint(1000, 9999)
            session.get(f"https://mpets.mobi/?action=food&rand={rand_food}")
        await update.message.reply_text("Питомец покормлен!")

    # Проверка возможности поиграть с питомцем
    if action_found["play"]:
        logging.info("Можно поиграть с питомцем, переходим по ссылке.")
        # Генерируем случайное значение для rand и переходим по ссылке
        rand_play = random.randint(1000, 9999)
        session.get(f"https://mpets.mobi/?action=play&rand={rand_play}")
        for _ in range(5):
            rand_play = random.randint(1000, 9999)
            session.get(f"https://mpets.mobi/?action=play&rand={rand_play}")
        await update.message.reply_text("Питомец поиграл!")

    # Переходим по ссылке выставки (6 раз)
    for _ in range(6):
        session.get("https://mpets.mobi/show")
    await update.message.reply_text("Питомец посетил выставку!")

    # После выставки проверяем, не уснул ли питомец
    if "Питомец устал и уснул" in response.text:
        await update.message.reply_text("Выставка не прошла, питомец уснул.")
        return COOKIES

    # Проверяем поляны на семена
    if check_seeds_found(response.text):
        await update.message.reply_text("Шанс найти семена найден. Переходим по ссылке.")
        for _ in range(6):
            session.get("https://mpets.mobi/glade_dig")

    # Проверяем прогулки
    if "Ваш питомец гуляет" in response.text:
        # Извлекаем время прогулки
        match = re.search(r"До конца прогулки осталось (\d+)ч (\d+)м", response.text)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            total_seconds = (hours * 60 * 60) + (minutes * 60)
            await update.message.reply_text(f"Питомец гуляет. Время до конца прогулки: {hours}ч {minutes}м.")
            await asyncio.sleep(total_seconds)
            await update.message.reply_text("Питомец завершил прогулку!")

    return ConversationHandler.END

# Основная часть с бота и настройками
def main():
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={COOKIES: [MessageHandler(filters.TEXT, cookies)]},
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
