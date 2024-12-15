import asyncio
import logging
import json
import os
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext
from aiohttp import ClientSession, CookieJar
from bs4 import BeautifulSoup

# Установите ваш токен бота
TOKEN = "7690678050:AAGBwTdSUNgE7Q6Z2LpE6481vvJJhetrO-4"

# Путь к файлу сессий
USERS_FILE = "users.txt"

# Разрешенные пользователи по ID
ALLOWED_USER_IDS = [1811568463, 630965641]

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Глобальная переменная для хранения сессий пользователей
user_sessions = {}

# Функция для отправки сообщений
async def send_message(update: Update, text: str):
    await update.message.reply_text(text)

# Команда старт для начала работы с ботом
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Управляй сессиями с помощью команд:\n"
                                    "/add - добавить новую сессию\n"
                                    "/del - удалить сессию\n"
                                    "/list - посмотреть все сессии\n"
                                    "/on - активировать сессию\n"
                                    "/off - деактивировать сессию\n"
                                    "/stats <имя_сессии> - проверить статистику питомца\n"
                                    "/get_user <имя_сессии> - узнать владельца сессии и куки\n"
                                    "/export - отправить файл с сессиями.")

# Функция для чтения данных из файла
def read_from_file():
    global user_sessions
    if not os.path.exists(USERS_FILE):
        return

    with open(USERS_FILE, "r") as file:
        lines = file.readlines()

    for line in lines:
        session_data = line.strip().split(" | ")

        # Проверка на наличие всех данных
        if len(session_data) != 3:
            logging.warning(f"Некорректная строка в файле: {line.strip()}")
            continue

        session_name, owner, cookies_json = session_data

        try:
            cookies = json.loads(cookies_json)  # Пробуем распарсить куки
        except json.JSONDecodeError:
            logging.error(f"Ошибка при парсинге JSON для сессии {session_name}: {cookies_json}")
            continue

        # Добавляем сессию в глобальное хранилище
        user_sessions[session_name] = {
            "owner": owner,
            "cookies": cookies,
            "active": False
        }

    logging.info("Информация о сессиях успешно загружена из файла.")

# Функция для записи данных в файл
def write_to_file(session_name, owner, cookies):
    with open(USERS_FILE, "a") as file:
        cookies_json = json.dumps(cookies)
        file.write(f"{session_name} | {owner} | {cookies_json}\n")
    logging.info(f"Сессия {session_name} добавлена в файл.")

# Команда для добавления новой сессии
async def add_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Использование: /add <имя_сессии> <куки в формате JSON>")
            return

        session_name = context.args[0]
        cookies_json = " ".join(context.args[1:])
        
        cookies = json.loads(cookies_json)
        if not cookies:
            await update.message.reply_text("Пожалуйста, отправьте куки в правильном формате JSON.")
            return

        # Создаём объект CookieJar для хранения и отправки куков
        jar = CookieJar()
        for cookie in cookies:
            jar.update_cookies({cookie['name']: cookie['value']})

        session = ClientSession(cookie_jar=jar)
        await session.__aenter__()

        # Сохраняем сессию и куки для пользователя
        if user_id not in user_sessions:
            user_sessions[user_id] = {}

        if session_name in user_sessions[user_id]:
            await update.message.reply_text(f"Сессия с именем {session_name} уже существует.")
        else:
            user_sessions[user_id][session_name] = {
                "session": session,
                "active": False,
                "owner": update.message.from_user.username,
                "cookies": cookies
            }

            # Записываем данные в файл
            write_to_file(session_name, update.message.from_user.username, cookies)
            await update.message.reply_text(f"Сессия {session_name} успешно добавлена!")
            logging.info(f"Сессия {session_name} добавлена для пользователя {update.message.from_user.username}.")

    except json.JSONDecodeError:
        await update.message.reply_text("Невозможно распарсить куки. Убедитесь, что они в формате JSON.")
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {e}")

# Команда для удаления сессии
async def remove_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /del <имя_сессии>")
        return

    session_name = context.args[0]

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        session = user_sessions[user_id].pop(session_name)
        await session["session"].__aexit__(None, None, None)
        await update.message.reply_text(f"Сессия {session_name} удалена.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для отображения всех сессий пользователя
async def list_sessions(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in user_sessions and user_sessions[user_id]:
        session_list = "\n".join([f"{name} - {'Активна' if session['active'] else 'Неактивна'}"
                                 for name, session in user_sessions[user_id].items()])
        await update.message.reply_text(f"Ваши активные сессии:\n{session_list}")
    else:
        await update.message.reply_text("У вас нет активных сессий.")

# Команда для активации сессии
async def activate_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /on <имя_сессии>")
        return

    session_name = context.args[0]

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        user_sessions[user_id][session_name]["active"] = True
        await update.message.reply_text(f"Сессия {session_name} активирована!")

        # Автоматически начать действия после активации сессии
        asyncio.create_task(auto_actions(user_sessions[user_id][session_name]["session"], session_name))
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для деактивации сессии
async def deactivate_session(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /off <имя_сессии>")
        return

    session_name = context.args[0]

    if user_id in user_sessions and session_name in user_sessions[user_id]:
        user_sessions[user_id][session_name]["active"] = False
        await update.message.reply_text(f"Сессия {session_name} деактивирована.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для получения информации о владельце сессии
async def get_user(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("У вас нет прав на использование этой команды.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Использование: /get_user <имя_сессии>")
        return

    session_name = context.args[0]

    if session_name in user_sessions:
        session_data = user_sessions[session_name]
        await update.message.reply_text(f"Сессия {session_name} принадлежит {session_data['owner']}.")
    else:
        await update.message.reply_text(f"Сессия {session_name} не найдена.")

# Экспорт всех сессий в файл
async def export_sessions(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("У вас нет прав на использование этой команды.")
        return

    try:
        with open(USERS_FILE, "rb") as file:
            await update.message.reply_document(InputFile(file, filename=USERS_FILE))
        await update.message.reply_text("Файл с сессиями успешно отправлен.")
    except FileNotFoundError:
        await update.message.reply_text("Файл с сессиями не найден.")

# Функция для получения статистики питомца
async def get_pet_stats(session: ClientSession):
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

# Основная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    # Загрузка сессий из файла
    read_from_file()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_session))
    application.add_handler(CommandHandler("del", remove_session))
    application.add_handler(CommandHandler("list", list_sessions))
    application.add_handler(CommandHandler("on", activate_session))
    application.add_handler(CommandHandler("off", deactivate_session))
    application.add_handler(CommandHandler("stats", get_pet_stats))
    application.add_handler(CommandHandler("get_user", get_user))
    application.add_handler(CommandHandler("export", export_sessions))

    # Запуск бота
    await application.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # Это позволяет использовать event loop в Jupyter или других средах, где он уже запущен
    asyncio.get_event_loop().run_until_complete(main())
