import asyncio
import logging
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from aiohttp import ClientSession, CookieJar
from bs4 import BeautifulSoup

# Установите ваш токен бота
TOKEN = "7689453735:AAHI8OfNGZzOM3fy9RQrXCjYRBHUKCXZAUY"

# Путь к файлу сессий
USERS_FILE = "users.txt"

# Разрешенные пользователи по ID
ALLOWED_USER_IDS = [1811568463, 630965641]

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Глобальная переменная для хранения сессий пользователей
user_sessions = {}
user_tasks = {}

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
                                    "Отправьте куки в формате JSON для авторизации.")

# Функция для чтения данных из файла
def read_from_file():
    if not os.path.exists(USERS_FILE):
        return []

    with open(USERS_FILE, "r") as file:
        lines = file.readlines()

    sessions = []
    for line in lines:
        session_data = line.strip().split(" | ")

        # Проверка на наличие всех данных
        if len(session_data) != 4:
            logging.warning(f"Некорректная строка в файле: {line.strip()}")
            continue

        try:
            cookies = json.loads(session_data[3])  # Пробуем распарсить куки
        except json.JSONDecodeError:
            logging.error(f"Ошибка при парсинге JSON для сессии: {session_data[0]}")
            continue  # Пропускаем некорректные строки

        sessions.append({
            "session_name": session_data[0],
            "owner": session_data[1],
            "user_id": int(session_data[2]),
            "cookies": cookies
        })

    return sessions
# Функция для записи данных в файл
def write_to_file(session_name, owner, user_id, cookies):
    with open(USERS_FILE, "a") as file:
        cookies_json = json.dumps(cookies)
        file.write(f"{session_name} | {owner} | {user_id} | {cookies_json}\n")
    logging.info(f"Сессия {session_name} добавлена в файл.")

def load_sessions():
    global user_sessions
    sessions = read_from_file()
    for session in sessions:
        # Преобразуем cookies в словарь
        cookies = convert_cookies_to_dict(session["cookies"]) if isinstance(session["cookies"], list) else session["cookies"]
        
        user_sessions.setdefault(session["user_id"], {})[session["session_name"]] = {
            "owner": session["owner"],
            "cookies": cookies,
            "active": False
        }


def convert_cookies_to_dict(cookies_list):
    # Преобразуем список объектов куки в словарь
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
    return cookies_dict


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

        # Сохраняем сессию и куки для пользователя
        if user_id not in user_sessions:
            user_sessions[user_id] = {}

        if session_name in user_sessions[user_id]:
            await update.message.reply_text(f"Сессия с именем {session_name} уже существует.")
        else:
            user_sessions[user_id][session_name] = {
                "owner": update.message.from_user.username,
                "cookies": cookies,
                "active": False
            }

            # Записываем данные в файл
            write_to_file(session_name, update.message.from_user.username, user_id, cookies)
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
        user_sessions[user_id].pop(session_name)
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
        task = asyncio.create_task(auto_actions(user_sessions[user_id][session_name]["cookies"], session_name))
        
        # Сохраняем задачу для дальнейшего отмены
        user_tasks[(user_id, session_name)] = task

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

        # Если задача существует, отменяем ее
        task = user_tasks.get((user_id, session_name))
        if task:
            task.cancel()
            del user_tasks[(user_id, session_name)]
            logging.info(f"Задача для сессии {session_name} отменена.")
        else:
            logging.warning(f"Задача для сессии {session_name} не найдена для отмены.")
    else:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")


# Команда для получения информации о владельце сессии
async def get_user(update: Update, context: CallbackContext):
    # Проверка, что пользователь имеет разрешение
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("У вас нет прав на использование этой команды.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Использование: /get_user <имя_сессии>")
        return

    session_name = context.args[0]

    session_info = read_from_file()
    for session in session_info:
        if session["session_name"] == session_name:
            response = f"Сессия: {session_name}\n"
            response += f"Владелец: {session['owner']}\n"
            response += f"Куки: {json.dumps(session['cookies'], indent=4)}"
            await send_message(update, response)
            return

    await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")

# Команда для получения статистики питомца
async def stats(update: Update, context: CallbackContext):
    # Проверяем, что команда передана с аргументами
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /stats <имя_сессии>")
        return

    session_name = context.args[0]
    user_id = update.message.from_user.id

    # Проверяем, существует ли сессия у пользователя
    if user_id not in user_sessions or session_name not in user_sessions[user_id]:
        await update.message.reply_text(f"Сессия с именем {session_name} не найдена.")
        return

    # Получаем куки из сессии
    cookies = user_sessions[user_id][session_name]["cookies"]

    # Если cookies представлены в виде списка, преобразуем их в словарь
    if isinstance(cookies, list):
        cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    else:
        cookies_dict = cookies

    # Создаем новую сессию для статистики
    async with ClientSession(cookie_jar=CookieJar()) as session:
        # Используем куки для авторизации
        session.cookie_jar.update_cookies(cookies_dict)

        # Получаем статистику питомца
        stats = await fetch_pet_stats(session)

        # Если статистика успешно получена, отправляем её
        if stats:
            await update.message.reply_text(stats)
        else:
            await update.message.reply_text(f"Не удалось получить статистику для сессии {session_name}.")

# Переименованная функция для получения статистики питомца
async def fetch_pet_stats(session: ClientSession):
    url = "https://mpets.mobi/profile"
    try:
        # Отправка GET запроса на страницу профиля питомца
        async with session.get(url) as response:
            if response.status != 200:
                return f"Ошибка при загрузке страницы профиля: {response.status}"

            page = await response.text()
            soup = BeautifulSoup(page, 'html.parser')

            # Парсим страницу, чтобы извлечь информацию о питомце
            stat_items = soup.find_all('div', class_='stat_item')

            if not stat_items:
                return "Не удалось найти элементы статистики."

            # Извлекаем данные о питомце
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
    except Exception as e:
        return f"Произошла ошибка при запросе статистики: {e}"

# Функция для автоматических действий
async def auto_actions(session_data, session_name):
    actions = [
        "https://mpets.mobi/?action=food",
        "https://mpets.mobi/?action=play",
        "https://mpets.mobi/show",
        "https://mpets.mobi/glade_dig",
        "https://mpets.mobi/show_coin_get"
    ]

    # Преобразуем cookies из списка в словарь, если session_data является списком
    if isinstance(session_data, list):
        cookies = {cookie['name']: cookie['value'] for cookie in session_data}
    else:
        cookies = session_data.get("cookies", {})

    # Создаем сессию aiohttp с использованием cookies
    cookie_jar = CookieJar()
    for cookie_name, cookie_value in cookies.items():
        cookie_jar.update_cookies({cookie_name: cookie_value})

    # Создаем новый ClientSession с куки
    async with ClientSession(cookie_jar=cookie_jar) as session:
        while True:
            # Проверяем, не отменена ли задача
            if asyncio.current_task().cancelled():
                logging.info(f"Задача для сессии {session_name} отменена.")
                return  # Выход из цикла, если задача была отменена

            # Переходы по первыми четырём ссылкам 6 раз с задержкой в 1 секунду
            for action in actions[:4]:
                for _ in range(6):  # Повторить переход 6 раз
                    await visit_url(session, action, session_name)
                    await asyncio.sleep(1)

            # Переход по последней ссылке 1 раз
            await visit_url(session, actions[4], session_name)

            # Переход по дополнительным ссылкам
            for i in range(10, 0, -1):
                url = f"https://mpets.mobi/go_travel?id={i}"
                await visit_url(session, url, session_name)
                await asyncio.sleep(1)

            # Пауза между циклами
            await asyncio.sleep(60)  # Задержка 60 секунд перед новым циклом
            
async def visit_url(session, url, session_name):
    try:
        # Запрос с использованием правильных куки
        async with session.get(url) as response:
            if response.status == 200:
                logging.info(f"[{session_name}] Переход по {url} прошел успешно!")
            else:
                logging.error(f"[{session_name}] Ошибка при переходе по {url}: {response.status}")
    except Exception as e:
        logging.error(f"[{session_name}] Ошибка при запросе к {url}: {e}")

# Основная функция для запуска бота
async def main():
    application = Application.builder().token(TOKEN).build()

    load_sessions()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_session))
    application.add_handler(CommandHandler("del", remove_session))
    application.add_handler(CommandHandler("list", list_sessions))
    application.add_handler(CommandHandler("on", activate_session))
    application.add_handler(CommandHandler("off", deactivate_session))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("get_user", get_user))

    # Запуск бота
    await application.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # Это позволяет использовать event loop в Jupyter или других средах, где он уже запущен
    asyncio.get_event_loop().run_until_complete(main())
