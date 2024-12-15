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

# Глобальные переменные для хранения сессий
user_sessions = {}

# Функция для отправки сообщений
async def send_message(update: Update, text: str):
    await update.message.reply_text(text)

# Команда старт для начала работы с ботом
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Используй /add для создания новой сессии, /del для удаления сессии, /stats для получения статистики, /go для запуска сессии.")

# Команда добавления сессии
async def add_session(update: Update, context: CallbackContext):
    logging.info(f"User {update.message.from_user.id} started adding a new session.")
    await update.message.reply_text("Отправьте куки в формате JSON для новой сессии.")
    return "WAITING_FOR_COOKIES"

# Получение куков
async def get_cookies(update: Update, context: CallbackContext):
    cookies_json = update.message.text.strip()
    logging.info(f"User {update.message.from_user.id} entered cookies.")

    try:
        cookies = json.loads(cookies_json)
        
        # Извлекаем только name и value
        cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}

        if not cookies_dict:
            await update.message.reply_text("Пожалуйста, отправьте валидные куки в формате JSON.")
            return "WAITING_FOR_COOKIES"
    except json.JSONDecodeError:
        await update.message.reply_text("Невозможно распарсить куки. Убедитесь, что они в формате JSON.")
        return "WAITING_FOR_COOKIES"

    # Сохраняем куки в user_data
    context.user_data['cookies'] = cookies_dict

    # Переход к следующему этапу: запрос имени сессии
    await update.message.reply_text("Теперь введите имя для новой сессии.")
    return "WAITING_FOR_SESSION_NAME"

# Получение имени сессии
async def get_session_name(update: Update, context: CallbackContext):
    session_name = update.message.text.strip()
    logging.info(f"User {update.message.from_user.id} entered session name: {session_name}")

    # Проверяем, не существует ли сессия с таким именем
    if session_name in user_sessions:
        await update.message.reply_text(f"Сессия с именем '{session_name}' уже существует. Попробуйте другое имя.")
        return "WAITING_FOR_SESSION_NAME"  # Ожидаем новое имя

    # Создаем сессию и сохраняем её
    cookies = context.user_data['cookies']
    jar = CookieJar()
    jar.update_cookies(cookies)  # Обновляем куки в CookieJar

    session = ClientSession(cookie_jar=jar)
    await session.__aenter__()

    # Сохраняем сессию в словарь с ключом имени сессии
    user_sessions[session_name] = {'session': session, 'cookies': cookies}

    await update.message.reply_text(f"Сессия '{session_name}' успешно создана!")
    return "SESSION_CREATED"

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

# Функция для перехода по ссылкам
async def visit_url(session, url, user_id, session_name):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                logging.info(f"Пользователь {user_id} (сессия '{session_name}') успешно перешел по {url}")
            else:
                logging.error(f"Пользователь {user_id} (сессия '{session_name}') не смог перейти по {url}: {response.status}")
    except Exception as e:
        logging.error(f"Ошибка при запросе к {url} для пользователя {user_id} (сессия '{session_name}'): {e}")

# Команда для запуска действий с выбранной сессией
async def go(update: Update, context: CallbackContext):
    session_name = ' '.join(context.args).strip()

    if session_name not in user_sessions:
        await update.message.reply_text(f"Сессия с именем '{session_name}' не найдена.")
        return

    session = user_sessions[session_name]['session']
    user_id = update.message.from_user.id
    actions = [
        "https://mpets.mobi/?action=food",
        "https://mpets.mobi/?action=play",
        "https://mpets.mobi/show",
        "https://mpets.mobi/glade_dig",
        "https://mpets.mobi/show_coin_get"
    ]

    for action in actions[:4]:
        for _ in range(6):
            await visit_url(session, action, user_id, session_name)
            await asyncio.sleep(1)

    await update.message.reply_text(f"Действия с сессией '{session_name}' завершены.")

# Основная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_session))
    application.add_handler(CommandHandler("del", del_session))
    application.add_handler(CommandHandler("list_sessions", list_sessions))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("go", go))

    # Обработчики сообщений для куков
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_cookies))

    # Запуск бота
    await application.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # Это позволяет использовать event loop в Jupyter или других средах, где он уже запущен
    asyncio.get_event_loop().run_until_complete(main())
