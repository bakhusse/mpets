import requests
from io import BytesIO
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
import logging
import asyncio
import nest_asyncio

# Состояния для ConversationHandler
LOGIN, PASSWORD, CAPTCHA = range(3)

# Ваш токен Telegram-бота
TOKEN = '7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4'

# Инициализация сессии
session = requests.Session()

# Логирование для отладки
logging.basicConfig(level=logging.DEBUG)

# Функция для получения капчи с сайта
def get_captcha():
    url = 'https://mpets.mobi/captcha'  # Примерный URL для капчи
    response = session.get(url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить капчу. Статус: {response.status_code}")
        return None
    
    captcha_image = response.content
    logging.info(f"Капча получена, размер: {len(captcha_image)} байт")
    
    # Попробуем преобразовать изображение в формат, который Telegram поддерживает
    try:
        image = Image.open(BytesIO(captcha_image))
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG')  # Сохраняем в PNG
        img_byte_arr.seek(0)  # Возвращаем указатель в начало
        return img_byte_arr
    except Exception as e:
        logging.error(f"Не удалось обработать капчу: {e}")
        return None

# Функция для авторизации с капчей
def authorize(login, password, captcha_solution):
    url = 'https://mpets.mobi/login'  # Примерный URL для авторизации
    data = {
        'login': login,
        'password': password,
        'captcha': captcha_solution
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = session.post(url, data=data, headers=headers, allow_redirects=True)

    logging.debug(f"Ответ на запрос авторизации: {response.status_code}, {response.text[:200]}...")  # Логирование ответа

    # Проверка на ошибку авторизации
    if response.status_code == 200:
        # Проверка на ошибки капчи или логина/пароля
        if "Неверная captcha" in response.text:
            logging.error("Неверная капча.")
            return "Неверная captcha"
        elif "Неправильное Имя или Пароль" in response.text:
            logging.error("Неправильное имя или пароль.")
            return "Неправильное имя или пароль"
        elif "error=" in response.url and "welcome" in response.url:
            # Обрабатываем редирект с ошибкой авторизации
            error_code = response.url.split('error=')[-1]
            logging.error(f"Ошибка авторизации, код ошибки: {error_code}")
            return f"Ошибка авторизации, код ошибки: {error_code}"
        else:
            # Проверяем, если редирект на главную страницу после успешной авторизации
            if "welcome" in response.url:
                return "success"
            else:
                logging.error("Неизвестная ошибка авторизации.")
                return "Неизвестная ошибка авторизации"
    else:
        logging.error(f"Ошибка при авторизации, статус: {response.status_code}")
        return f"Ошибка при авторизации, статус: {response.status
