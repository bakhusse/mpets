import requests
from io import BytesIO
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
    return captcha_image

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
        return f"Ошибка при авторизации, статус: {response.status_code}"

# Обработка команды /start
async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Привет! Давай начнем авторизацию. Введи логин:')
    return LOGIN

# Обработка ввода логина
async def login(update: Update, context: CallbackContext) -> int:
    user_login = update.message.text
    context.user_data['login'] = user_login
    await update.message.reply_text('Теперь введи пароль:')
    return PASSWORD

# Обработка ввода пароля
async def password(update: Update, context: CallbackContext) -> int:
    user_password = update.message.text
    context.user_data['password'] = user_password

    # Отправляем запрос на сайт для получения капчи
    captcha_image = get_captcha()

    if captcha_image is None:
        await update.message.reply_text("Не удалось получить капчу. Попробуйте позже.")
        return ConversationHandler.END

    # Отправляем капчу пользователю
    await update.message.reply_text('Реши капчу:')
    await update.message.reply_photo(photo=BytesIO(captcha_image))

    return CAPTCHA

# Обработка решения капчи
async def captcha(update: Update, context: CallbackContext) -> int:
    captcha_solution = update.message.text.strip()

    # Получаем логин и пароль из контекста
    login = context.user_data['login']
    password = context.user_data['password']

    # Пытаемся авторизовать пользователя
    result = authorize(login, password, captcha_solution)

    # Обработка различных типов ошибок
    if result == "success":
        await update.message.reply_text('Авторизация успешна!')
        return ConversationHandler.END
    elif "Ошибка авторизации" in result:  # Если ошибка авторизации
        await update.message.reply_text(f'{result}. Попробуйте снова.')
        return LOGIN  # Попросить ввести логин снова
    elif result == "Неверная captcha":
        await update.message.reply_text('Ошибка: Неверная капча. Попробуйте снова.')
        return LOGIN  # Попросить ввести логин снова
    elif result == "Неправильное Имя или Пароль":
        await update.message.reply_text('Ошибка: Неправильное имя или пароль. Попробуйте снова.')
        return LOGIN  # Попросить ввести логин снова
    else:
        await update.message.reply_text(f'Ошибка при авторизации: {result}. Попробуйте снова.')
        return LOGIN  # Попросить ввести логин снова

# Функция завершения
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Авторизация отменена.')
    return ConversationHandler.END

# Основная асинхронная функция для запуска бота
async def main():
    # Создаем и запускаем бота
    application = Application.builder().token(TOKEN).build()

    # Определяем ConversationHandler для обработки пошаговой авторизации
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
            CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, captcha)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conversation_handler)

    # Запускаем бота
    await application.run_polling()

# Запускаем бота через await в Google Colab
if __name__ == "__main__":
    nest_asyncio.apply()  # Это позволяет запускать асинхронный код в уже существующем цикле событий

    # Теперь запускаем бота
    asyncio.get_event_loop().run_until_complete(main())
