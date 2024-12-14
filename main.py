import asyncio
import requests
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
import logging
import colorlog  # Для цветного логирования
import re
import nest_asyncio  # Для работы с уже существующим циклом событий
from PIL import Image  # Для работы с изображениями
import os  # Для работы с файлами

# Состояния для ConversationHandler
LOGIN, PASSWORD, CAPTCHA = range(3)

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
    
    # Сохранение капчи как файл
    captcha_filename = os.path.join(CAPTCHA_FOLDER, 'captcha.png')
    with open(captcha_filename, 'wb') as f:
        f.write(captcha_image)
    logging.info(f"Капча сохранена как {captcha_filename}")
    
    # Возвращаем путь к сохраненному файлу
    return captcha_filename

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

    # Логирование полного ответа на запрос
    logging.debug(f"Ответ на запрос авторизации:\n{response.text}")  # Печать всего текста ответа

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
            logging.error(f"Неизвестная ошибка авторизации. Ответ: {response.text}")
            return "Неизвестная ошибка авторизации", None
    else:
        logging.error(f"Ошибка при авторизации, статус: {response.status_code}")
        return f"Ошибка при авторизации, статус: {response.status_code}", None

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

# Функция для отправки капчи в Telegram
async def send_captcha(update: Update, context: CallbackContext, captcha_filename):
    with open(captcha_filename, 'rb') as file:
        await update.message.reply_photo(photo=file)
    logging.info("Капча отправлена в Telegram.")

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
    captcha_filename = get_captcha(session)

    if captcha_filename is None:
        await update.message.reply_text("Не удалось получить капчу. Попробуйте позже.")
        return ConversationHandler.END

    # Отправляем капчу пользователю
    await update.message.reply_text('Реши капчу:')
    await send_captcha(update, context, captcha_filename)

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

    if result == "Неверная captcha":
        await update.message.reply_text(f"Капча неверная! Попробуй снова.")
        return CAPTCHA

    if result == "success":
        # Проверяем наличие изображения на странице
        if check_image_on_page(page_html):
            await update.message.reply_text('Авторизация успешна! Изображение подтверждено, вы на главной странице сайта: https://mpets.mobi/')
        else:
            await update.message.reply_text('Авторизация успешна, но изображение не найдено. Повторите попытку.')
        return ConversationHandler.END
    else:
        await update.message.reply_text(f"Ошибка: {result}. Попробуйте снова.")
        return ConversationHandler.END

# Главная функция
async def main():
    # Используем nest_asyncio для обработки циклов событий в Jupyter
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
    asyncio.get_event_loop().run_until_complete(main())
