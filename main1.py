import asyncio
import logging
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from aiohttp import ClientSession, CookieJar
from bs4 import BeautifulSoup

# Установите ваш токен бота
TOKEN = "7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4"

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Глобальные переменные для хранения сессий и cookies по именам сессий
user_sessions = {}

# Функция для отправки сообщений
async def send_message(update: Update, text: str):
    await update.message.reply_text(text)

# Команда старт для начала работы с ботом
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Используй /add для создания новой сессии, /del для удаления сессии, и /stats для получения статистики.")

# Команда добавления сессии
async def add_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Шаг 1: Получить имя сессии
    await update.message.reply_text("Введите имя для новой сессии:")

    # Ожидаем имя сессии
    session_name = await get_user_input(update, "Введите имя для новой сессии:")

    # Шаг 2: Проверяем, не существует ли сессия с таким именем
    if session_name in user_sessions:
        await update.message.reply_text(f"Сессия с именем '{session_name}' уже существует. Попробуйте другое имя.")
        return

    # Шаг 3: Получаем куки
    await update.message.reply_text(f"Отправьте куки в формате JSON для сессии '{session_name}'.")

    cookies_json = await get_user_input(update, "Отправьте куки в формате JSON:")

    try:
        cookies = json.loads(cookies_json)
        if not cookies:
            await update.message.reply_text("Пожалуйста, отправьте валидные куки в формате JSON.")
            return
    except json.JSONDecodeError:
        await update.message.reply_text("Невозможно распарсить куки. Убедитесь, что они в формате JSON.")
        return

    # Создаем объект CookieJar для хранения куков
    jar = CookieJar()
    for cookie in cookies:
        jar.update_cookies({cookie['name']: cookie['value']})

    # Создаём сессию для данного пользователя
    session = ClientSession(cookie_jar=jar)
    await session.__aenter__()

    # Сохраняем сессию в словарь с ключом user_id и именем сессии
    user_sessions[session_name] = {'session': session, 'cookies': cookies}

    await update.message.reply_text(f"Сессия '{session_name}' успешно создана!")

# Команда удаления сессии
async def del_session(update: Update, context: CallbackContext):
    session_name = ' '.join(context.args).strip()

    if session_name in user_sessions:
        # Закрываем сессию
        session = user_sessions[session_name]['session']
        await session.__aexit__(None, None, None)
        del user_sessions[session_name]
        await update.message.reply_text(f"Сессия '{session_name}' успешно удалена.")
    else:
        await update.message.reply_text(f"Сессия с именем '{session_name}' не найдена.")

# Команда для отображения всех доступных сессий
async def list_sessions(update: Update, context: CallbackContext):
    if not user_sessions:
        await update.message.reply_text("У вас нет активных сессий.")
        return

    session_names = "\n".join(user_sessions.keys())
    await update.message.reply_text(f"Доступные сессии:\n{session_names}")

# Функция для получения ввода от пользователя
async def get_user_input(update: Update, prompt: str):
    await send_message(update, prompt)

    # Ожидаем текст от пользователя
    response = await update.message.reply_text("Жду вашего ответа...")
    return response.text

# Функция для получения статистики питомца
async def get_pet_stats(session_name):
    if session_name not in user_sessions:
        return "Сессия не установлена."

    session = user_sessions[session_name]['session']
    url = "https://mpets.mobi/profile"
    async with session.get(url) as response:
        if response.status != 200:
            return f"Ошибка при загрузке страницы профиля: {response.status}"

        page = await response.text()
    soup = BeautifulSoup(page, 'html.parser')

    # Парсим страницу, чтобы извлечь информацию о питомце
    stat_items = soup.find_all('div', class_='stat_item')
    
    if not stat_items:
        return "Не удалось найти элементы статистики."

    pet_name = stat_items[0].find('a', class_='darkgreen_link')
    if not pet_name:
        return "Не удалось найти имя питомца."
    pet_name = pet_name.text.strip()

    pet_level = stat_items[0].text.split(' ')[-2]  # Уровень питомца

    experience = "Не найдено"
    for item in stat_items:
        if 'Опыт:' in item.text:
            experience = item.text.strip().split('Опыт:')[-1].strip()
            break

    beauty = "Не найдено"
    for item in stat_items:
        if 'Красота:' in item.text:
            beauty = item.text.strip().split('Красота:')[-1].strip()
            break

    coins = "Не найдено"
    for item in stat_items:
        if 'Монеты:' in item.text:
            coins = item.text.strip().split('Монеты:')[-1].strip()
            break

    hearts = "Не найдено"
    for item in stat_items:
        if 'Сердечки:' in item.text:
            hearts = item.text.strip().split('Сердечки:')[-1].strip()
            break

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
    session_name = ' '.join(context.args).strip()

    if session_name not in user_sessions:
        await update.message.reply_text(f"Сессия с именем '{session_name}' не найдена.")
        return

    stats = await get_pet_stats(session_name)
    await send_message(update, stats)

# Основная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_session))
    application.add_handler(CommandHandler("del", del_session))
    application.add_handler(CommandHandler("list", list_sessions))
    application.add_handler(CommandHandler("stats", stats))

    # Запуск бота
    await application.run_polling()

if __name__ == "__main__":
    # Применяем nest_asyncio для работы с Google Colab
    import nest_asyncio
    nest_asyncio.apply()  # Это позволяет использовать event loop в Jupyter или других средах, где он уже запущен
    asyncio.get_event_loop().run_until_complete(main())
