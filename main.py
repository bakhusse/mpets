import time
import logging
import requests
import pytesseract
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from telegram import Bot, Update
from telegram.ext import CommandHandler, MessageHandler, Filters, Updater, ConversationHandler, CallbackContext
import schedule

# Конфигурация
TELEGRAM_TOKEN = '7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4'  # Ваш токен

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Ступени состояния диалога с пользователем
LOGIN, PASSWORD, CAPTCHA = range(3)

# Устанавливаем параметры для Selenium
def get_driver():
    options = Options()
    options.add_argument("--headless")  # Включаем headless-режим
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service('/usr/bin/chromedriver'), options=options)
    return driver

# Получение капчи с сайта
def get_captcha_image(driver):
    captcha_image_element = driver.find_element(By.XPATH, '//img[@class="captcha-image"]')
    captcha_image_url = captcha_image_element.get_attribute('src')
    response = requests.get(captcha_image_url)
    img = Image.open(BytesIO(response.content))
    return img

# Распознавание текста на капче с помощью pytesseract
def solve_captcha(image):
    captcha_text = pytesseract.image_to_string(image, config='--psm 6')
    return captcha_text.strip()

# Авторизация на сайте
def login(driver, username, password, captcha_solution):
    driver.get('https://mpets.mobi/welcome')
    driver.implicitly_wait(5)
    
    # Вводим логин и пароль
    username_field = driver.find_element(By.NAME, 'login')
    password_field = driver.find_element(By.NAME, 'password')
    captcha_field = driver.find_element(By.NAME, 'captcha')
    
    username_field.send_keys(username)
    password_field.send_keys(password)
    captcha_field.send_keys(captcha_solution)
    
    # Нажимаем кнопку "Войти"
    login_button = driver.find_element(By.NAME, 'submit')
    login_button.click()
    driver.implicitly_wait(5)

# Проверка наличия изображения на странице
def check_page_for_image(driver):
    try:
        driver.find_element(By.XPATH, '//img[@class="some-image-class"]')
        return True
    except:
        return False

# Получение логина пользователя
def start(update, context):
    update.message.reply_text('Привет! Пожалуйста, введи свой логин.')
    return LOGIN

# Получение пароля пользователя
def get_login(update, context):
    context.user_data['login'] = update.message.text
    update.message.reply_text('Теперь введи свой пароль.')
    return PASSWORD

# Получение капчи от пользователя
def get_password(update, context):
    context.user_data['password'] = update.message.text
    update.message.reply_text('Я получил пароль. Я отправлю тебе капчу, пожалуйста, реши её и введи текст.')
    
    # Запускаем Selenium драйвер
    driver = get_driver()

    # Получаем капчу с сайта и отправляем пользователю
    captcha_image = get_captcha_image(driver)
    update.message.reply_photo(photo=captcha_image)
    
    return CAPTCHA

# Обработка решения капчи
def get_captcha(update, context):
    captcha_solution = update.message.text
    login = context.user_data['login']
    password = context.user_data['password']
    
    # Пытаемся выполнить логин
    driver = get_driver()
    login(driver, login, password, captcha_solution)

    # Проверка наличия картинки
    if check_page_for_image(driver):
        logger.info("\033[92m[INFO] Картинка найдена на странице\033[0m")
        update.message.reply_text('Картинка найдена на странице! Теперь нажмем кнопки...')
        
        # Логика нажатия кнопок (пример: нажимаем все кнопки на странице)
        buttons = driver.find_elements(By.XPATH, '//button')
        for button in buttons:
            button.click()
            time.sleep(1)  # Пауза между нажатием кнопок
        
        update.message.reply_text('Кнопки нажаты успешно!')
    else:
        update.message.reply_text('Картинка не найдена на странице.')
        logger.error("\033[91m[ERROR] Картинка не найдена на странице\033[0m")

    # Закрытие браузера
    driver.quit()

    return ConversationHandler.END

# Завершение диалога
def cancel(update, context):
    update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

# Настройка Telegram бота
def main():
    # Настройка бота
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Обработчики команд
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOGIN: [MessageHandler(Filters.text & ~Filters.command, get_login)],
            PASSWORD: [MessageHandler(Filters.text & ~Filters.command, get_password)],
            CAPTCHA: [MessageHandler(Filters.text & ~Filters.command, get_captcha)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conversation_handler)

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
