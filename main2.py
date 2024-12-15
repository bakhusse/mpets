import asyncio
import logging
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from aiohttp import ClientSession
from bs4 import BeautifulSoup

# Установите ваш токен бота
TOKEN = "7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4"

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Глобальные переменные для хранения сессии и cookies
cookies = None
session = None

# Функция для отправки сообщений
async def send_message(update: Update, text: str):
    await update.message.reply_text(text)

# Команда старт для начала работы с ботом
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Отправьте куки в формате JSON для авторизации.")

# Команда остановки сессии
async def stop(update: Update, context: CallbackContext):
    global session, cookies
    session = None
    cookies = None
    await update.message.reply_text("Сессия остановлена, отправьте новые куки для другого аккаунта.")

# Функция для обработки куки и авторизации
async def set_cookies(update: Update, context: CallbackContext):
    global cookies, session
    try:
        # Получаем куки из текста сообщения
        cookies_json = update.message.text.strip()

        if not cookies_json:
            await update.message.reply_text("Пожалуйста, отправьте куки в правильном формате JSON.")
            return

        # Пытаемся распарсить переданные куки как JSON
        cookies = json.loads(cookies_json)
        if not cookies:
            await update.message.reply_text("Пожалуйста, отправьте куки в правильном формате JSON.")
            return
    except json.JSONDecodeError:
        await update.message.reply_text("Невозможно распарсить куки. Убедитесь, что они в формате JSON.")
        return

    # Создаем сессию
    session = await ClientSession().__aenter__()
    await update.message.reply_text("Куки получены, сессия начата!")

    # Автоматизация действий
    asyncio.create_task(auto_actions())

# Функция для получения статистики питомца
async def get_pet_stats():
    global session, cookies
    if not session:
        return "Сессия не установлена."

    # Собираем куки в строку для передачи в запросах
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    headers = {
        'Cookie': '; '.join([f"{key}={value}" for key, value in cookies_dict.items()])
    }

    url = "https://mpets.mobi/profile"
    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            return f"Ошибка при загрузке страницы профиля: {response.status}"

        page = await response.text()

    # Пытаемся парсить страницу с профилем
    soup = BeautifulSoup(page, 'html.parser')

    # Ищем все элементы с классом stat_item
    stat_items = soup.find_all('div', class_='stat_item')
    
    if not stat_items:
        return "Не удалось найти элементы статистики."

    # Получаем никнейм и уровень из первого элемента
    pet_name = stat_items[0].find('a', class_='darkgreen_link')
    if not pet_name:
        return "Не удалось найти имя питомца."
    pet_name = pet_name.text.strip()

    # Получаем уровень питомца из текста первого элемента
    pet_level = stat_items[0].text.split(' ')[-2]  # Уровень питомца

    # Получаем опыт
    experience = "Не найдено"
    for item in stat_items:
        if 'Опыт:' in item.text:
            experience = item.text.strip().split('Опыт:')[-1].strip()
            break

    # Получаем красоту
    beauty = "Не найдено"
    for item in stat_items:
        if 'Красота:' in item.text:
            beauty = item.text.strip().split('Красота:')[-1].strip()
            break

    # Получаем монеты
    coins = "Не найдено"
    for item in stat_items:
        if 'Монеты:' in item.text:
            coins = item.text.strip().split('Монеты:')[-1].strip()
            break

    # Получаем сердечки
    hearts = "Не найдено"
    for item in stat_items:
        if 'Сердечки:' in item.text:
            hearts = item.text.strip().split('Сердечки:')[-1].strip()
            break

    # Получаем информацию о VIP-аккаунте
    vip_status = "Не найдено"
    for item in stat_items:
        if 'VIP-аккаунт:' in item.text:
            vip_status = item.text.strip().split('VIP-аккаунт:')[-1].strip()
            break

    stats = f"Никнейм и уровень: {pet_name}, {pet_level} уровень\n"
    stats += f"Опыт: {experience}\nКрасота: {beauty}\n"
    stats += f"Монеты: {coins}\nСердечки: {hearts}\n"
    stats += f"VIP-аккаунт/Премиум-аккаунт: {vip_status}"

    return stats


# Команда для получения статистики питомца
async def stats(update: Update, context: CallbackContext):
    stats = await get_pet_stats()
    await send_message(update, stats)

# Функция для перехода по ссылкам
async def visit_url(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                logging.info(f"Переход по {url} прошел успешно!")
            else:
                logging.error(f"Ошибка при переходе по {url}: {response.status}")
    except Exception as e:
        logging.error(f"Ошибка при запросе к {url}: {e}")

# Функция для автоматических действий
async def auto_actions():
    global session, cookies
    if not session:
        return

    actions = [
        "https://mpets.mobi/?action=food",
        "https://mpets.mobi/?action=play",
        "https://mpets.mobi/show",
        "https://mpets.mobi/glade_dig",
        "https://mpets.mobi/show_coin_get"
    ]

    # Переход по ссылке 6 раз
    for action in actions[:4]:
        for _ in range(6):
            await visit_url(session, action)
            await asyncio.sleep(1)  # Задержка 1 секунда между переходами

    # Переход по ссылке show_coin_get 1 раз
    await visit_url(session, actions[4])

    # Переход по ссылкам go_travel с id от 10 до 1
    for i in range(10, 0, -1):
        url = f"https://mpets.mobi/go_travel?id={i}"
        await visit_url(session, url)
        await asyncio.sleep(1)  # Задержка 1 секунда между переходами

    # Задержка 60 секунд между циклами
    await asyncio.sleep(60)

    # Повторный цикл
    await auto_actions()

# Основная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_cookies))

    # Запуск бота
    await application.run_polling()

if __name__ == "__main__":
    # Запуск polling без использования asyncio.run()
    import nest_asyncio
    nest_asyncio.apply()  # Это позволяет использовать event loop в Jupyter или других средах, где он уже запущен
    asyncio.get_event_loop().run_until_complete(main())
