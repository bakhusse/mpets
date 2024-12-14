import requests
from io import BytesIO
from PIL import Image
import pytesseract
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
import logging
import asyncio
import nest_asyncio
import colorlog  # Для цветного логирования
import re

# Состояния для ConversationHandler
LOGIN, PASSWORD, CAPTCHA = range(3)

# Ваш токен Telegram-бота
TOKEN = '7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4'

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

# Функция для получения капчи с сайта
def get_captcha(session):
    url = 'https://mpets.mobi/captcha'  # Примерный URL для капчи
    logging.info(f"Отправка запроса на получение капчи: {url}")
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
        return img_byte_arr, image  # Возвращаем и сам байтовый массив, и изображение для OCR
    except Exception as e:
        logging.error(f"Не удалось обработать капчу: {e}")
        return None

# Функция для распознавания текста капчи
def solve_captcha(image):
    try:
        captcha_text = pytesseract.image_to_string(image, config='--psm 6').strip()
        logging.info(f"Распознанная капча: {captcha_text}")
        return captcha_text
    except Exception as e:
        logging.error(f"Ошибка при распознавании капчи: {e}")
        return None

# Функция для авторизации с капчей
def authorize(session, login, password, captcha_solution):
    url = 'https://mpets.mobi/login'  # URL для авторизации
    data = {
        'name': login,
        'password': password,
        'captcha': captcha_solution
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    logging.info(f"Отправка запроса на авторизацию с данными: {data}")
    response = session.post(url, data=data, headers=headers)

    logging.debug(f"Ответ на запрос авторизации: {response.status_code}, {response.text[:200]}...")  # Логирование ответа

    # Проверка на ошибку авторизации
    if response.status_code == 200:
        if "Неверная captcha" in response.text:
            logging.error("Неверная капча.")
            return "Неверная captcha", None
        elif "Неправильное Имя или Пароль" in response.text:
            logging.error("Неправильное имя или пароль.")
            return "Неправильное имя или пароль", None
        elif "Oops! Your session is expired" in response.text:
            # Если сессия истекла, перезапускаем процесс
            logging.error("Сессия истекла. Перезапуск авторизации.")
            return "Сессия истекла. Пожалуйста, начните с /start.", None
        elif "mpets.mobi" in response.url:
            # Если авторизация успешна, проверяем на редирект на главную страницу
            logging.info("Авторизация успешна! Переход на главную страницу.")
            return "success", response.text  # Возвращаем HTML-страницу
        else:
            logging.error(f"Неизвестная ошибка авторизации. Ответ: {response.text[:200]}")
            return "Неизвестная ошибка авторизации", None
    else:
        logging.error(f"Ошибка при авторизации, статус: {response.status_code}")
        return f"Ошибка при авторизации, статус: {response.status_code}", None

# Эмуляция сессии через cookies и необходимые шаги
def start_session(update, context):
    session = create_new_session()
    context.user_data['session'] = session  # Сохраняем сессию в контексте пользователя

    # Выполняем запрос на страницу welcome и сохраняем cookies
    welcome_url = "https://mpets.mobi/welcome"
    logging.info(f"Запрос на страницу {welcome_url}")
    response = session.get(welcome_url)
    
    if response.status_code != 200:
        logging.error(f"Не удалось получить страницу welcome. Статус: {response.status_code}")
        return None
    # Сохраняем cookies для дальнейших запросов
    logging.info(f"Сессия сохранена, cookies: {session.cookies.get_dict()}")

    return session

# Обработка команды /start
async def start(update: Update, context: CallbackContext) -> int:
    logging.info("Начало процесса авторизации.")
    
    # Создаем новую сессию сразу при старте
    session = start_session(update, context)
    
    if session is None:
        await update.message.reply_text("Не удалось начать сессию. Попробуйте снова.")
        return ConversationHandler.END

    await update.message.reply_text('Привет! Давай начнем авторизацию. Введи логин:')
    return LOGIN

# Обработка ввода логина
async def login(update: Update, context: CallbackContext) -> int:
    user_login = update.message.text
    context.user_data['login'] = user_login
    logging.info(f"Пользователь ввел логин: {user_login}")
    await update.message.reply_text('Теперь введи пароль:')
    return PASSWORD

# Обработка ввода пароля
async def password(update: Update, context: CallbackContext) -> int:
    user_password = update.message.text
    context.user_data['password'] = user_password
    logging.info(f"Пользователь ввел пароль.")

    # Получаем сессию из контекста
    session = context.user_data['session']

    # Отправляем запрос на сайт для получения капчи
    captcha_image, image = get_captcha(session)

    if captcha_image is None:
        await update.message.reply_text("Не удалось получить капчу. Попробуйте позже.")
        return ConversationHandler.END

    # Пробуем распознать капчу с помощью OCR
    captcha_solution = solve_captcha(image)
    if captcha_solution:
        logging.info(f"Распознанная капча: {captcha_solution}")
        await update.message.reply_text(f"Решение капчи: {captcha_solution}")

    # Отправляем капчу пользователю
    await update.message.reply_text('Реши капчу:')
    await update.message.reply_photo(photo=captcha_image)

    return CAPTCHA

# Обработка решения капчи
async def captcha(update: Update, context: CallbackContext) -> int:
    captcha_solution = update.message.text.strip()
    logging.info(f"Пользователь ввел капчу: {captcha_solution}")

    # Получаем логин и пароль из контекста
    login = context.user_data['login']
    password = context.user_data['password']

    # Получаем сессию из контекста
    session = context.user_data['session']

    # Пытаемся авторизовать пользователя
    result, page_html = authorize(session, login, password, captcha_solution)

    # Обработка различных типов ошибок
    if result == "success":
        await update.message.reply_text(f"Авторизация успешна: {result}")
        return ConversationHandler.END
    else:
        await update.message.reply_text(f"Ошибка: {result}. Попробуйте снова.")
        return ConversationHandler.END

# Главная функция
async def main():
    nest_asyncio.apply()

    application = Application.builder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOGIN: [MessageHandler(filters.TEXT, login)],
            PASSWORD: [MessageHandler(filters.TEXT, password)],
            CAPTCHA: [MessageHandler(filters.TEXT, captcha)],
        },
        fallbacks=[],
    )

    application.add_handler(conversation_handler)

    logging.info("Бот запущен.")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
