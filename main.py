import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
import nest_asyncio
from bs4 import BeautifulSoup

# Настройка цветного логирования
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()

logging.basicConfig(level=logging.DEBUG, handlers=[console_handler])
logger = logging.getLogger()

# Состояния для ConversationHandler
LOGIN, PASSWORD, CAPTCHA = range(3)

# Ваш токен Telegram-бота (замените на ваш реальный токен)
TOKEN = '7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4'

# Функция авторизации (отправка запроса на сайт)
def authorize_on_site(username, password, captcha):
    session = requests.Session()
    
    # Первая страница авторизации
    login_url = 'https://mpets.mobi/login'
    login_page = session.get(login_url)
    
    # Извлекаем параметры для авторизации (например, CSRF токен)
    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrf_token'})['value']  # Пример
    
    # Данные для отправки
    payload = {
        'username': username,
        'password': password,
        'captcha': captcha,
        'csrf_token': csrf_token
    }
    
    # Отправляем запрос на авторизацию
    response = session.post(login_url, data=payload)
    
    # Проверяем, прошла ли авторизация
    if 'Oops! Your session is expired' in response.text:
        return False
    return True

# Функция, которая будет запускаться по команде /start
async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Добро пожаловать! Пожалуйста, введите ваш логин.")
    return LOGIN  # Переходим к вводу логина

# Обработка ввода логина
async def login(update: Update, context: CallbackContext) -> int:
    context.user_data['login'] = update.message.text
    await update.message.reply_text("Пожалуйста, введите ваш пароль.")
    return PASSWORD  # Переходим к вводу пароля

# Обработка ввода пароля
async def password(update: Update, context: CallbackContext) -> int:
    context.user_data['password'] = update.message.text
    # Отправляем запрос на сервер, чтобы получить капчу
    session = requests.Session()
    response = session.get('https://mpets.mobi/login')
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Извлекаем капчу, если она есть
    captcha_url = soup.find('img', {'id': 'captcha_img'})['src']
    context.user_data['captcha_url'] = captcha_url
    await update.message.reply_text(f"Пожалуйста, введите капчу. Вот изображение: {captcha_url}")
    
    return CAPTCHA  # Переходим к вводу капчи

# Обработка ввода капчи
async def captcha(update: Update, context: CallbackContext) -> int:
    captcha_solution = update.message.text
    login = context.user_data['login']
    password = context.user_data['password']
    
    # Проверяем авторизацию на сайте
    if authorize_on_site(login, password, captcha_solution):
        await update.message.reply_text("Авторизация прошла успешно!")
        return ConversationHandler.END  # Завершаем процесс
    else:
        await update.message.reply_text("Ошибка авторизации. Попробуйте снова команду /start.")
        return ConversationHandler.END  # Завершаем процесс

# Функция для отмены процесса
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Процесс авторизации отменен.")
    return ConversationHandler.END

# Главная функция
async def main():
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд и состояний
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password)],
            CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, captcha)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conversation_handler)

    # Запуск бота
    await application.run_polling()

# Настроим asyncio для работы в Google Colab (если нужно)
nest_asyncio.apply()

# Запуск бота
if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
