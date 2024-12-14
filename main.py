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

# Функция для извлечения времени прогулки
def extract_travel_time(page_html):
    # Ищем шаблон "До конца прогулки осталось 6ч 10м"
    match = re.search(r"До конца прогулки осталось (\d+)ч (\d+)м", page_html)
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

    # Перед авторизацией проверяем возможность действий (кормление, игра)
    action_found, food_link, play_link = check_action_links(response.text)
    logging.info(f"Доступные действия: {action_found}")
    
    # Проверка возможности покормить питомца
    if action_found["food"]:
        logging.info("Можно покормить питомца, переходим по ссылке.")
        # Генерируем случайное значение для rand и переходим по ссылке
        rand_food = random.randint(1000, 9999)
        session.get(f"https://mpets.mobi/?action=food&rand={rand_food}")  # Переходим по ссылке кормления 6 раз
        for _ in range(5):
            rand_food = random.randint(1000, 9999)
            session.get(f"https://mpets.mobi/?action=food&rand={rand_food}")
        await update.message.reply_text("Питомец покормлен!")
    else:
        await update.message.reply_text("Действие для кормления не найдено.")
    
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
    else:
        await update.message.reply_text("Действие для игры не найдено.")
    
    # Переход по ссылке выставки 6 раз
    logging.info("Переход по ссылке выставки.")
    for _ in range(6):
        session.get("https://mpets.mobi/show")
    
    await update.message.reply_text("Выставка посещена!")

    # После проверок проверка на прогулку
    logging.info("Проверка состояния прогулки питомца.")
    
    # Выполняем запрос к странице с информацией о прогулке
    response = session.get("https://mpets.mobi/travel")  # Выполняем запрос для получения времени прогулки

    # Проверяем, что прогулка активна
    if response.status_code == 200:
        if check_travel_complete(response.text):
            await update.message.reply_text("Прогулка завершена!")
        else:
            # Извлекаем оставшееся время
            travel_time = extract_travel_time(response.text)
            if travel_time:
                await update.message.reply_text(f"До конца прогулки осталось {travel_time // 3600}ч {(travel_time % 3600) // 60}м.")
                await asyncio.sleep(travel_time)
                await update.message.reply_text("Прогулка завершена!")

    # Выполняем прогулку, если еще не завершена
    await update.message.reply_text("Отправляем питомца гулять!")
    for duration in range(10, 0, -1):
        session.get(f"https://mpets.mobi/go_travel?id={duration}")
        await asyncio.sleep(1)  # Пауза между переходами для уменьшения нагрузки

    # Проверка полянки для поиска семян
    logging.info("Проверка полянки для поиска семян.")
    response = session.get("https://mpets.mobi/glade")
    if check_seeds_found(response.text):
        for _ in range(6):
            session.get("https://mpets.mobi/glade_dig")
        await update.message.reply_text("Семена найдены!")

    return START

# Создание приложения бота
application = Application.builder().token(TOKEN).build()

# Хендлеры для команд
application.add_handler(CommandHandler("start", start))

# Хендлер для получения cookies
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cookies))

# Запуск бота
if __name__ == '__main__':
    application.run_polling()
