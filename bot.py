import logging
import sqlite3
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import io
from datetime import datetime, timedelta
import asyncio
from calendar import monthrange
import os  # ДОБАВЛЕНО для работы с файлами

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ConversationHandler,
    CallbackQueryHandler
)
from gigachat import GigaChat


# ===== ПАТЧ ДЛЯ PYTHON 3.13/3.11 =====
from telegram.ext import Updater

_original_updater_init = Updater.__init__

def patched_updater_init(self, bot, update_queue=None):
    try:
        _original_updater_init(self, bot, update_queue)
    except AttributeError:
        self.bot = bot
        self.update_queue = update_queue
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._stop_event = None
        self._polling_cleanup_cb = None
        self._initialized = False
        self._application = None

Updater.__init__ = patched_updater_init
# =================================

# =====================================================================
# 0. НАСТРОЙКИ
# =====================================================================
TELEGRAM_BOT_TOKEN = "8203916057:AAGpQFT_DVCFHFwJrKmu-pC2-3xm0p16Ej0"
GIGA_CHAT_API_KEY = "MDE5YTZkOTctZjJkYi03ZmEyLWFjOGEtODRhNTljZjNjMjlkOjk3ZWMyYmMzLWE0MDItNGMxNC05NjkzLTJkNWZlYzBkOTFlNQ=="
DATABASE_NAME = "bot_database"
ADMIN_USERNAME = "Loony"
ADMIN_PASSWORD = "2112"
PAYMENT_LINK = "https://www.tinkoff.ru/rm/r_NLApoIzDiE.OaumdvlKtW/uKABk9392"

# =====================================================================
# 0.1. ФУНКЦИЯ ДЛЯ ОТПРАВКИ КАРТИНОК (ДОБАВЛЕНА)
# =====================================================================
def image_exists(image_path: str) -> bool:
    """Проверяет, существует ли файл картинки"""
    return os.path.exists(image_path)

async def send_image_if_exists(update: Update, image_path: str, caption: str = None):
    """Отправляет картинку, если файл существует"""
    if image_exists(image_path):
        try:
            with open(image_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode='Markdown'
                )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке картинки {image_path}: {e}")
            return False
    else:
        logger.warning(f"Картинка не найдена: {image_path}")
        return False

# =====================================================================
# 1. СОСТОЯНИЯ ДЛЯ ConversationHandler
# =====================================================================
(
    GETTING_AGE,
    GETTING_HEIGHT,
    GETTING_WEIGHT,
    EDITING_PROFILE_CHOICE,
    EDIT_AGE,
    EDIT_HEIGHT,
    EDIT_WEIGHT,
    RATION_DURATION,
    RATION_GOAL,
    CALORIE_MEAL_TYPE,
    CALORIE_AMOUNT,
    SUBSCRIPTION_MENU_CHOICE,
    ADMIN_LOGIN,
    ADMIN_PASSWORD_STATE,
    ADMIN_MENU,
    CALORIE_HISTORY_DATE,
    CALORIE_GOAL_SETTING,
    ADMIN_SEARCH_USER,
    ADMIN_USER_CONTROL,
    DELETE_CALORIE_RECORD,
    NAVIGATE_RATION,
) = range(21)

# =====================================================================
# 2. ЛОГИРОВАНИЕ
# =====================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =====================================================================
# 3. ФУНКЦИИ РАБОТЫ С БАЗОЙ ДАННЫХ
# =====================================================================

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE NOT NULL,
            username VARCHAR,
            first_name VARCHAR,
            last_name VARCHAR,
            age INTEGER,
            height REAL,
            weight REAL,
            bmi REAL,
            bmi_recommendation TEXT,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            calorie_goal INTEGER DEFAULT 2000,
            protein_goal INTEGER DEFAULT 0,
            fat_goal INTEGER DEFAULT 0,
            carbs_goal INTEGER DEFAULT 0
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Payment_status (
            id_payment_status INTEGER PRIMARY KEY,
            name VARCHAR UNIQUE NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS type_subscriptions (
            id_type_subscription INTEGER PRIMARY KEY,
            name VARCHAR UNIQUE NOT NULL,
            duration_days INTEGER
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Subscriptions (
            id_subscription INTEGER PRIMARY KEY,
            type_subscription_id INTEGER,
            user_id INTEGER,
            start_date DATETIME,
            end_date DATETIME,
            active BOOLEAN DEFAULT FALSE,
            payment_status_id INTEGER,
            price REAL,
            price_currency VARCHAR,
            FOREIGN KEY (type_subscription_id) REFERENCES type_subscriptions(id_type_subscription),
            FOREIGN KEY (user_id) REFERENCES Users(user_id),
            FOREIGN KEY (payment_status_id) REFERENCES Payment_status(id_payment_status)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CalorieLog (
            id_log INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            log_date DATE NOT NULL,
            meal_type VARCHAR NOT NULL,
            food_description TEXT,
            calories INTEGER NOT NULL,
            protein REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS WeightHistory (
            id_history INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            record_date DATE NOT NULL,
            change_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ProfileHistory (
            id_history INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            age INTEGER,
            height REAL,
            weight REAL,
            bmi REAL,
            change_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            change_type VARCHAR(50),
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CalorieGoalsHistory (
            id_history INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            calorie_goal INTEGER,
            change_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        );
    """)

    cursor.execute("INSERT OR IGNORE INTO type_subscriptions (id_type_subscription, name, duration_days) VALUES (1, 'Free', 0)")
    cursor.execute("INSERT OR IGNORE INTO type_subscriptions (id_type_subscription, name, duration_days) VALUES (2, 'Weekly 200', 7)")
    cursor.execute("INSERT OR IGNORE INTO type_subscriptions (id_type_subscription, name, duration_days) VALUES (3, 'Monthly 350', 30)")
    cursor.execute("INSERT OR IGNORE INTO type_subscriptions (id_type_subscription, name, duration_days) VALUES (4, 'Trial 1 day', 1)")

    cursor.execute("INSERT OR IGNORE INTO Payment_status (id_payment_status, name) VALUES (1, 'Pending')")
    cursor.execute("INSERT OR IGNORE INTO Payment_status (id_payment_status, name) VALUES (2, 'Paid')")
    cursor.execute("INSERT OR IGNORE INTO Payment_status (id_payment_status, name) VALUES (3, 'Failed')")

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована.")

def get_user_data_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, telegram_id, username, first_name, last_name, age, height, weight, bmi, bmi_recommendation, registration_date FROM Users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user_data = cursor.fetchone()
    conn.close()
    return user_data

def add_user_from_telegram(telegram_id, username=None, first_name=None, last_name=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM Users WHERE telegram_id = ?", (telegram_id,))
    existing_user = cursor.fetchone()
    if existing_user:
        conn.close()
        return existing_user[0]
    cursor.execute(
        "INSERT INTO Users (telegram_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
        (telegram_id, username, first_name, last_name)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Новый пользователь добавлен: telegram_id={telegram_id}, user_id={user_id}")
    return user_id

def debug_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\n=== ТАБЛИЦЫ В БАЗЕ ДАННЫХ ===")
        for table in tables:
            print(f"  - {table[0]}")
        cursor.execute("PRAGMA table_info(Users)")
        columns = cursor.fetchall()
        print("\n=== СТРУКТУРА ТАБЛИЦЫ Users ===")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        cursor.execute("SELECT COUNT(*) FROM Users")
        user_count = cursor.fetchone()[0]
        print(f"\n=== КОЛИЧЕСТВО ПОЛЬЗОВАТЕЛЕЙ: {user_count} ===")
        if user_count > 0:
            cursor.execute("SELECT telegram_id, username, age, height, weight FROM Users LIMIT 5")
            users = cursor.fetchall()
            print("\n=== ПЕРВЫЕ 5 ПОЛЬЗОВАТЕЛЕЙ ===")
            for user in users:
                print(f"  ID: {user[0]}, Username: {user[1]}, Age: {user[2]}, Height: {user[3]}, Weight: {user[4]}")
    except sqlite3.Error as e:
        print(f"Ошибка при отладке БД: {e}")
    finally:
        conn.close()

def add_weight_history(user_id, weight):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO WeightHistory (user_id, weight, record_date) VALUES (?, ?, DATE('now'))",
            (user_id, weight)
        )
        conn.commit()
        logger.info(f"Добавлена запись в историю веса для user_id={user_id}: {weight} кг")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении истории веса для user_id={user_id}: {e}")
    finally:
        conn.close()

def add_profile_history(user_id, age=None, height=None, weight=None, bmi=None, change_type="manual_update"):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ProfileHistory (user_id, age, height, weight, bmi, change_type) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, age, height, weight, bmi, change_type)
        )
        conn.commit()
        logger.info(f"Добавлена запись в историю профиля для user_id={user_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении истории профиля для user_id={user_id}: {e}")
    finally:
        conn.close()

def add_calorie_goal_history(user_id, calorie_goal=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO CalorieGoalsHistory (user_id, calorie_goal) VALUES (?, ?)",
            (user_id, calorie_goal)
        )
        conn.commit()
        logger.info(f"Добавлена запись в историю целей калорий для user_id={user_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении истории целей калорий для user_id={user_id}: {e}")
    finally:
        conn.close()

def get_weight_history(user_id, limit=10):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weight, record_date, change_date
        FROM WeightHistory
        WHERE user_id = ?
        ORDER BY record_date DESC, change_date DESC
        LIMIT ?
    """, (user_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

def get_weight_statistics(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weight, record_date FROM WeightHistory
        WHERE user_id = ?
        ORDER BY record_date ASC, change_date ASC
        LIMIT 1
    """, (user_id,))
    first_record = cursor.fetchone()
    cursor.execute("""
        SELECT weight, record_date FROM WeightHistory
        WHERE user_id = ?
        ORDER BY record_date DESC, change_date DESC
        LIMIT 1
    """, (user_id,))
    last_record = cursor.fetchone()
    cursor.execute("""
        SELECT weight, record_date FROM WeightHistory
        WHERE user_id = ?
        ORDER BY record_date ASC, change_date ASC
    """, (user_id,))
    all_records = cursor.fetchall()
    conn.close()
    if not all_records:
        return None
    weights = [record[0] for record in all_records]
    dates = [record[1] for record in all_records]
    total_change = weights[-1] - weights[0] if len(weights) > 1 else 0
    return {
        'first_weight': weights[0] if first_record else None,
        'first_date': dates[0] if first_record else None,
        'last_weight': weights[-1] if last_record else None,
        'last_date': dates[-1] if last_record else None,
        'total_change': total_change,
        'total_records': len(weights),
        'min_weight': min(weights) if weights else None,
        'max_weight': max(weights) if weights else None,
        'weight_history': list(zip(weights, dates))
    }

def get_profile_history(user_id, limit=5):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT age, height, weight, bmi, change_date, change_type
        FROM ProfileHistory
        WHERE user_id = ?
        ORDER BY change_date DESC
        LIMIT ?
    """, (user_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

def get_calorie_goal_history(user_id, limit=5):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT calorie_goal, change_date
        FROM CalorieGoalsHistory
        WHERE user_id = ?
        ORDER BY change_date DESC
        LIMIT ?
    """, (user_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

def update_user_profile_data(user_id, age=None, height=None, weight=None, bmi=None, bmi_recommendation=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT age, height, weight FROM Users WHERE user_id = ?", (user_id,))
    current_data = cursor.fetchone()
    if current_data:
        current_age, current_height, current_weight = current_data
        updates = []
        values = []
        if age is not None:
            updates.append("age = ?")
            values.append(age)
        if height is not None:
            updates.append("height = ?")
            values.append(height)
        if weight is not None:
            updates.append("weight = ?")
            values.append(weight)
            add_weight_history(user_id, weight)
        if bmi is not None:
            updates.append("bmi = ?")
            values.append(bmi)
        if bmi_recommendation is not None:
            updates.append("bmi_recommendation = ?")
            values.append(bmi_recommendation)
        if updates:
            set_clause = ", ".join(updates)
            values.append(user_id)
            try:
                cursor.execute(f"UPDATE Users SET {set_clause} WHERE user_id = ?", values)
                add_profile_history(
                    user_id,
                    age if age is not None else current_age,
                    height if height is not None else current_height,
                    weight if weight is not None else current_weight,
                    bmi,
                    "manual_update"
                )
                conn.commit()
                logger.info(f"Профиль пользователя user_id={user_id} обновлен и сохранен в историю.")
            except sqlite3.Error as e:
                logger.error(f"Ошибка при обновлении профиля пользователя user_id={user_id}: {e}")
                conn.rollback()
    conn.close()

def update_calorie_goal(user_id, calorie_goal=None, protein_goal=None, fat_goal=None, carbs_goal=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    updates = []
    values = []
    if calorie_goal is not None:
        updates.append("calorie_goal = ?")
        values.append(calorie_goal)
        add_calorie_goal_history(user_id, calorie_goal)
    if protein_goal is not None:
        updates.append("protein_goal = ?")
        values.append(protein_goal)
    if fat_goal is not None:
        updates.append("fat_goal = ?")
        values.append(fat_goal)
    if carbs_goal is not None:
        updates.append("carbs_goal = ?")
        values.append(carbs_goal)
    if not updates:
        conn.close()
        return
    set_clause = ", ".join(updates)
    values.append(user_id)
    try:
        cursor.execute(f"UPDATE Users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
        logger.info(f"Цели по калориям обновлены для user_id={user_id} и сохранены в историю.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении целей по калориям для user_id={user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_user_profile_completeness(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT age, height, weight FROM Users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        age, height, weight = user_data
        return all([age is not None, height is not None, weight is not None])
    return False

def get_user_progress_stats(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT weight FROM Users
        WHERE user_id = ? AND weight IS NOT NULL
        ORDER BY registration_date LIMIT 1
    """, (user_id,))
    initial_weight = cursor.fetchone()
    cursor.execute("SELECT weight FROM Users WHERE user_id = ?", (user_id,))
    current_weight = cursor.fetchone()
    cursor.execute("""
        SELECT COUNT(DISTINCT log_date) FROM CalorieLog
        WHERE user_id = ?
    """, (user_id,))
    active_days = cursor.fetchone()
    conn.close()
    return {
        'initial_weight': initial_weight[0] if initial_weight else None,
        'current_weight': current_weight[0] if current_weight else None,
        'active_days': active_days[0] if active_days else 0
    }

def get_weekly_calories(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT log_date, SUM(calories)
        FROM CalorieLog
        WHERE user_id = ? AND log_date >= date('now', '-7 days')
        GROUP BY log_date
        ORDER BY log_date DESC
    """, (user_id,))
    weekly_calories = cursor.fetchall()
    cursor.execute("""
        SELECT AVG(daily_calories) FROM (
            SELECT SUM(calories) as daily_calories
            FROM CalorieLog
            WHERE user_id = ?
            GROUP BY log_date
        )
    """, (user_id,))
    avg_calories = cursor.fetchone()
    conn.close()
    return weekly_calories, avg_calories[0] if avg_calories and avg_calories[0] else 0

def get_user_subscription_status(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ts.name, s.end_date
            FROM Subscriptions s
            JOIN type_subscriptions ts ON s.type_subscription_id = ts.id_type_subscription
            WHERE s.user_id = ? AND s.active = TRUE AND s.end_date > CURRENT_TIMESTAMP
            ORDER BY s.end_date DESC LIMIT 1
        """, (user_id,))
        result = cursor.fetchone()
        if result:
            sub_name = result[0]
            if sub_name == 'Weekly 200':
                return 'week_200'
            if sub_name == 'Monthly 350':
                return 'month_350'
            if sub_name == 'Trial 1 day':
                return 'trial'
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении статуса подписки для user_id={user_id}: {e}")
    finally:
        conn.close()
    return 'free'

def activate_subscription(user_id, subscription_type_name, duration_days):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_type_subscription FROM type_subscriptions WHERE name = ?", (subscription_type_name,))
        type_sub_result = cursor.fetchone()
        if not type_sub_result:
            logger.error(f"Тип подписки '{subscription_type_name}' не найден.")
            return False
        type_subscription_id = type_sub_result[0]
        cursor.execute("SELECT id_payment_status FROM Payment_status WHERE name = 'Paid'")
        payment_status_result = cursor.fetchone()
        if not payment_status_result:
            logger.error("Статус оплаты 'Paid' не найден.")
            return False
        paid_status_id = payment_status_result[0]
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)
        cursor.execute("UPDATE Subscriptions SET active = FALSE WHERE user_id = ?", (user_id,))
        cursor.execute("""
            INSERT INTO Subscriptions (type_subscription_id, user_id, start_date, end_date, active, payment_status_id, price, price_currency)
            VALUES (?, ?, ?, ?, TRUE, ?, ?, ?)
        """, (type_subscription_id, user_id, start_date, end_date, paid_status_id,
              200 if subscription_type_name == 'Weekly 200' else 350 if subscription_type_name == 'Monthly 350' else 0, "RUB"))
        conn.commit()
        logger.info(f"Подписка '{subscription_type_name}' активирована для user_id={user_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при активации подписки для user_id={user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def deactivate_subscription(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE Subscriptions SET active = FALSE WHERE user_id = ? AND active = TRUE",
            (user_id,)
        )
        conn.commit()
        logger.info(f"Подписка принудительно отключена для user_id={user_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при отключении подписки user_id={user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def activate_trial(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_subscription FROM Subscriptions WHERE user_id = ? AND type_subscription_id = 4",
        (user_id,)
    )
    if cursor.fetchone():
        conn.close()
        return False
    cursor.execute("SELECT id_payment_status FROM Payment_status WHERE name = 'Paid'")
    paid_status_id = cursor.fetchone()[0]
    start_date = datetime.now()
    end_date = start_date + timedelta(days=1)
    cursor.execute("""
        INSERT INTO Subscriptions (type_subscription_id, user_id, start_date, end_date, active, payment_status_id, price, price_currency)
        VALUES (4, ?, ?, ?, TRUE, ?, 0, 'RUB')
    """, (user_id, start_date, end_date, paid_status_id))
    cursor.execute("UPDATE Subscriptions SET active = FALSE WHERE user_id = ? AND id_subscription != ?",
                   (user_id, cursor.lastrowid))
    conn.commit()
    conn.close()
    return True

def record_calorie(user_id, log_date, meal_type, calories, food_description=None, protein=0, fat=0, carbs=0):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO CalorieLog (user_id, log_date, meal_type, food_description, calories, protein, fat, carbs) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, log_date, meal_type, food_description, calories, protein, fat, carbs)
        )
        conn.commit()
        logger.info(f"Калории записаны для user_id={user_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при записи калорий для user_id={user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_daily_calorie_summary(user_id, log_date):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    summary_data = {}
    try:
        cursor.execute("""
            SELECT meal_type, SUM(calories), SUM(protein), SUM(fat), SUM(carbs)
            FROM CalorieLog
            WHERE user_id = ? AND log_date = ?
            GROUP BY meal_type
        """, (user_id, log_date))
        results = cursor.fetchall()
        summary_data = {
            meal_type: {
                'calories': calories,
                'protein': protein,
                'fat': fat,
                'carbs': carbs
            } for meal_type, calories, protein, fat, carbs in results
        }
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении сводки калорий для user_id={user_id}: {e}")
    finally:
        conn.close()
    return summary_data

def get_calorie_history(user_id, start_date, end_date):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT log_date, SUM(calories), SUM(protein), SUM(fat), SUM(carbs)
        FROM CalorieLog
        WHERE user_id = ? AND log_date BETWEEN ? AND ?
        GROUP BY log_date
        ORDER BY log_date DESC
    """, (user_id, start_date, end_date))
    history = cursor.fetchall()
    conn.close()
    return history

def get_user_calorie_goal(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT calorie_goal FROM Users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0] or 2000
    return 2000

def get_period_statistics(user_id, period_days):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    history = get_calorie_history(user_id, start_date, end_date)
    goal = get_user_calorie_goal(user_id)
    total_calories = sum(day[1] for day in history) if history else 0
    total_days = len(history)
    avg_calories = total_calories / total_days if total_days > 0 else 0
    goal_days = sum(1 for day in history if day[1] <= goal) if history else 0
    goal_percentage = (goal_days / total_days * 100) if total_days > 0 else 0
    return {
        'period_days': period_days,
        'total_calories': total_calories,
        'total_days': total_days,
        'avg_calories': avg_calories,
        'goal_days': goal_days,
        'goal_percentage': goal_percentage,
        'history': history
    }

def generate_user_calorie_csv(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT log_date, meal_type, food_description, calories, protein, fat, carbs
        FROM CalorieLog
        WHERE user_id = ?
        ORDER BY log_date DESC, meal_type
    """, (user_id,))
    calorie_data = cursor.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Дата', 'Прием пищи', 'Описание', 'Калории', 'Белки (г)', 'Жиры (г)', 'Углеводы (г)'])
    for entry in calorie_data:
        writer.writerow(entry)
    return output.getvalue()

def get_all_users_data():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            u.user_id,
            u.telegram_id,
            u.username,
            u.first_name,
            u.last_name,
            u.age,
            u.height,
            u.weight,
            u.bmi,
            u.bmi_recommendation,
            u.registration_date
        FROM Users u
        ORDER BY u.registration_date DESC
    """)
    users_data = cursor.fetchall()
    conn.close()
    return users_data

def get_all_calorie_data():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cl.id_log,
            u.telegram_id,
            u.username,
            cl.log_date,
            cl.meal_type,
            cl.calories
        FROM CalorieLog cl
        JOIN Users u ON cl.user_id = u.user_id
        ORDER BY cl.log_date DESC, u.telegram_id
    """)
    calorie_data = cursor.fetchall()
    conn.close()
    return calorie_data

def get_all_subscriptions_data():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            s.id_subscription,
            u.telegram_id,
            u.username,
            ts.name as subscription_type,
            s.start_date,
            s.end_date,
            s.active,
            ps.name as payment_status,
            s.price,
            s.price_currency
        FROM Subscriptions s
        JOIN Users u ON s.user_id = u.user_id
        JOIN type_subscriptions ts ON s.type_subscription_id = ts.id_type_subscription
        JOIN Payment_status ps ON s.payment_status_id = ps.id_payment_status
        ORDER BY s.start_date DESC
    """)
    subscriptions_data = cursor.fetchall()
    conn.close()
    return subscriptions_data

def generate_users_csv():
    users_data = get_all_users_data()
    calorie_data = get_all_calorie_data()
    subscriptions_data = get_all_subscriptions_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['=== ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ==='])
    writer.writerow(['ID', 'Telegram ID', 'Username', 'Имя', 'Фамилия', 'Возраст', 'Рост', 'Вес', 'ИМТ', 'Рекомендация', 'Дата регистрации'])
    for user in users_data:
        writer.writerow(user)
    writer.writerow([])
    writer.writerow(['=== ДАННЫЕ О КАЛОРИЯХ ==='])
    writer.writerow(['ID записи', 'Telegram ID', 'Username', 'Дата', 'Тип приема пищи', 'Калории'])
    for calorie in calorie_data:
        writer.writerow(calorie)
    writer.writerow([])
    writer.writerow(['=== ДАННЫЕ О ПОДПИСКАХ ==='])
    writer.writerow(['ID подписки', 'Telegram ID', 'Username', 'Тип подписки', 'Дата начала', 'Дата окончания', 'Активна', 'Статус оплата', 'Цена', 'Валюта'])
    for subscription in subscriptions_data:
        writer.writerow(subscription)
    return output.getvalue()

# =====================================================================
# 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================

def calculate_bmi(height_cm, weight_kg):
    if height_cm is None or weight_kg is None or height_cm <= 0 or weight_kg <= 0:
        return None
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 2)

def get_bmi_recommendation(bmi):
    if bmi is None:
        return "Невозможно рассчитать ИМТ."
    elif bmi < 18.5:
        return "Ваш ИМТ ниже нормы. Рекомендуется проконсультироваться с врачом для набора веса."
    elif 18.5 <= bmi <= 24.9:
        return "Отличный результат! Ваш ИМТ в пределах нормы."
    elif 25 <= bmi <= 29.9:
        return "Ваш ИМТ указывает на избыточный вес. Рекомендуется скорректировать питание и добавить физическую активность."
    else:
        return "Ваш ИМТ указывает на ожирение. Крайне рекомендуется консультация с врачом и диетологом."

def get_bmi_category(bmi):
    if bmi is None:
        return "Неизвестно"
    elif bmi < 18.5:
        return "недостаточный вес"
    elif 18.5 <= bmi <= 24.9:
        return "норма"
    elif 25 <= bmi <= 29.9:
        return "избыточный вес"
    else:
        return "ожирение"

def calculate_calorie_needs(age, height, weight, goal="maintenance"):
    if not all([age, height, weight]):
        return None
    base_calories = 10 * weight + 6.25 * height - 5 * age + 5
    maintenance_calories = base_calories * 1.375
    if goal == "weight_loss":
        return maintenance_calories - 400
    elif goal == "weight_gain":
        return maintenance_calories + 400
    else:
        return maintenance_calories

async def ask_giga_chat(prompt: str) -> str:
    """
    Отправляет запрос к GigaChat и возвращает ответ
    """
    try:
        from gigachat import GigaChat
        
        logger.info("Отправляю запрос к GigaChat...")
        
        with GigaChat(credentials=GIGA_CHAT_API_KEY, verify_ssl_certs=False) as giga:
            response = giga.chat(prompt)
            result = response.choices[0].message.content
            logger.info("Получен ответ от GigaChat")
            return result
            
    except ImportError:
        logger.error("Библиотека gigachat не установлена")
        return "❌ Ошибка: библиотека GigaChat не установлена. Выполните: pip install gigachat"
        
    except Exception as e:
        logger.error(f"Ошибка при обращении к GigaChat: {e}")
        return f"❌ Ошибка при генерации рациона. Попробуйте позже.\n\nДетали: {str(e)}"

# =====================================================================
# 5. ОБРАБОТЧИКИ ТЕЛЕГРАМ (ПОЛЬЗОВАТЕЛЬСКИЕ)
# =====================================================================

async def send_main_menu(update: Update, context):
    """Отправляет главное меню"""
    keyboard = [
        [KeyboardButton("🍽️ Питание"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("📊 Калорийность"), KeyboardButton("💳 Подписка")]
    ]
    await update.message.reply_text(
        "Выберите раздел:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def start(update: Update, context):
    """Обработчик команды /start с приветственной картинкой!"""
    telegram_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    user_id = add_user_from_telegram(telegram_id, username, first_name, last_name)
    
    # ===== 1. ОТПРАВЛЯЕМ ПРИВЕТСТВЕННУЮ КАРТИНКУ =====
    await send_image_if_exists(
        update, 
        "images/welcome.png",
        "🍽️ **Добро пожаловать в бота-помощника по питанию!**\n\n"
        "Я помогу вам:\n"
        "• Составить персональный рацион\n"
        "• Отслеживать калории\n"
        "• Достигать целей по весу\n\n"
        "👇 Давайте настроим ваш профиль!"
    )
    
    user_data = get_user_data_by_telegram_id(telegram_id)
    if user_data and user_data[5] is None:
        await update.message.reply_text("Для начала заполните свои данные.")
        await update.message.reply_text("Введите ваш возраст:")
        context.user_data['current_user_id'] = user_id
        return GETTING_AGE
    else:
        await send_main_menu(update, context)
        return ConversationHandler.END

async def help_command(update: Update, context):
    await update.message.reply_text("Я могу помочь вам с питанием, профилем и учетом калорий.")

async def cancel_conversation(update: Update, context):
    await update.message.reply_text("Действие отменено. Возвращаюсь в главное меню.")
    await send_main_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END

async def get_age(update: Update, context):
    try:
        age = int(update.message.text)
        if 1 <= age <= 120:
            context.user_data['age'] = age
            await update.message.reply_text("Теперь введите ваш рост (в сантиметрах):")
            return GETTING_HEIGHT
        else:
            await update.message.reply_text("Пожалуйста, введите корректный возраст (от 1 до 120).")
            return GETTING_AGE
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число для возраста.")
        return GETTING_AGE

async def get_height(update: Update, context):
    try:
        height = float(update.message.text)
        if 1 <= height <= 250:
            context.user_data['height'] = height
            await update.message.reply_text("И, наконец, ваш вес (в килограммах):")
            return GETTING_WEIGHT
        else:
            await update.message.reply_text("Пожалуйста, введите корректный рост (от 1 до 250 см).")
            return GETTING_HEIGHT
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число для роста.")
        return GETTING_HEIGHT

async def get_weight(update: Update, context):
    user_id = context.user_data.get('current_user_id')
    if not user_id:
        await update.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте снова, используя команду /start.")
        return ConversationHandler.END
    try:
        weight = float(update.message.text)
        if 1 <= weight <= 500:
            age = context.user_data.get('age')
            height = context.user_data.get('height')
            if age is None or height is None:
                await update.message.reply_text("Произошла ошибка. Попробуйте снова, используя команду /start.")
                return ConversationHandler.END
            bmi = calculate_bmi(height, weight)
            recommendation = get_bmi_recommendation(bmi)
            update_user_profile_data(user_id=user_id, age=age, height=height, weight=weight, bmi=bmi, bmi_recommendation=recommendation)
            await update.message.reply_text(f"Отлично! Ваши данные обновлены:\n"
                                            f"Возраст: {age} лет\n"
                                            f"Рост: {height} см\n"
                                            f"Вес: {weight} кг\n"
                                            f"ИМТ: {bmi} ({get_bmi_category(bmi).capitalize()})")
            await update.message.reply_text(recommendation)
            context.user_data.pop('age', None)
            context.user_data.pop('height', None)
            context.user_data.pop('current_user_id', None)
            await send_main_menu(update, context)
            return ConversationHandler.END
        else:
            await update.message.reply_text("Пожалуйста, введите корректный вес (от 1 до 500 кг).")
            return GETTING_WEIGHT
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число для веса.")
        return GETTING_WEIGHT

# --- РЕДАКТИРОВАНИЕ ПРОФИЛЯ ---
async def edit_profile_start(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return ConversationHandler.END
    user_id, _, _, _, _, age, height, weight, bmi, _, _ = user_data
    current_info = "📋 **Текущие данные профиля:**\n\n"
    current_info += f"• Возраст: {age if age else '❌ Не заполнено'}\n"
    current_info += f"• Рост: {height if height else '❌ Не заполнено'} см\n"
    current_info += f"• Вес: {weight if weight else '❌ Не заполнено'} кг\n"
    if all([age, height, weight]):
        current_info += f"• ИМТ: {bmi:.1f}\n"
    keyboard = [
        [KeyboardButton("📝 Изменить возраст"), KeyboardButton("📝 Изменить рост")],
        [KeyboardButton("📝 Изменить вес"), KeyboardButton("📋 История изменений")],
        [KeyboardButton("⬅️ Назад в профиль")]
    ]
    await update.message.reply_text(
        current_info,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data['current_user_id'] = user_id
    return EDITING_PROFILE_CHOICE

async def edit_profile_choice(update: Update, context):
    text = update.message.text
    user_id = context.user_data.get('current_user_id')
    
    if not user_id:
        telegram_id = update.effective_user.id
        user_data = get_user_data_by_telegram_id(telegram_id)
        if user_data:
            user_id = user_data[0]
            context.user_data['current_user_id'] = user_id
        else:
            await update.message.reply_text("Ошибка: Не могу определить ваш ID. Попробуйте /start.")
            return ConversationHandler.END
    
    if text == "📝 Изменить возраст":
        context.user_data['editing_field'] = 'age'
        await update.message.reply_text("Введите новый возраст (от 1 до 120 лет):")
        return EDIT_AGE
    elif text == "📝 Изменить рост":
        context.user_data['editing_field'] = 'height'
        await update.message.reply_text("Введите новый рост (в сантиметрах, от 50 до 250 см):")
        return EDIT_HEIGHT
    elif text == "📝 Изменить вес":
        context.user_data['editing_field'] = 'weight'
        await update.message.reply_text("Введите новый вес (в килограммах, от 20 до 300 кг):")
        return EDIT_WEIGHT
    elif text == "📋 История изменений":
        await show_profile_history(update, context)
        return ConversationHandler.END
    elif text == "⬅️ Назад в профиль":
        await update.message.reply_text("Редактирование отменено.")
        await show_profile(update, context)
        context.user_data.pop('current_user_id', None)
        return ConversationHandler.END
    elif text == "✏️ Изменить данные":
        return await edit_profile_start(update, context)
    elif text == "📝 Изменить еще данные":
        return await edit_profile_start(update, context)
    else:
        await update.message.reply_text("Некорректный выбор. Пожалуйста, выберите из меню.")
        return EDITING_PROFILE_CHOICE

async def edit_age_handler(update: Update, context):
    text = update.message.text
    
    menu_buttons = [
        "✏️ Изменить данные", "📊 Детальная статистика", "🎯 Мои цели", "📈 График веса",
        "⬅️ Назад в профиль", "⬅️ Назад в главное меню", "📝 Изменить возраст", 
        "📝 Изменить рост", "📝 Изменить вес", "📋 История изменений", "📝 Изменить еще данные",
        "🍽️ Питание", "👤 Профиль", "📊 Калорийность", "💳 Подписка"
    ]
    
    if text in menu_buttons:
        await update.message.reply_text("❌ Редактирование отменено.")
        if text == "⬅️ Назад в профиль" or text == "✏️ Изменить данные":
            await show_profile(update, context)
        elif text == "⬅️ Назад в главное меню":
            await send_main_menu(update, context)
        elif text in ["📝 Изменить возраст", "📝 Изменить рост", "📝 Изменить вес", "📝 Изменить еще данные"]:
            await edit_profile_start(update, context)
        else:
            await handle_message(update, context)
        context.user_data.pop('current_user_id', None)
        return ConversationHandler.END
    
    try:
        age = int(text)
        if 1 <= age <= 120:
            user_id = context.user_data.get('current_user_id')
            if not user_id:
                await update.message.reply_text("Ошибка: Не могу определить ваш ID.")
                return ConversationHandler.END
            user_data = get_user_data_by_telegram_id(update.effective_user.id)
            if not user_data:
                await update.message.reply_text("Ошибка: Данные пользователя не найдены.")
                return ConversationHandler.END
            _, _, _, _, _, current_age, height, weight, _, _, _ = user_data
            if height and weight:
                bmi = calculate_bmi(height, weight)
                recommendation = get_bmi_recommendation(bmi)
                update_user_profile_data(
                    user_id=user_id,
                    age=age,
                    bmi=bmi,
                    bmi_recommendation=recommendation
                )
                await update.message.reply_text(f"✅ Возраст успешно изменен на {age} лет.\nВаш ИМТ: {bmi:.1f}")
            else:
                update_user_profile_data(user_id=user_id, age=age)
                await update.message.reply_text(f"✅ Возраст успешно изменен на {age} лет.")
            keyboard = [
                [KeyboardButton("📝 Изменить еще данные")],
                [KeyboardButton("⬅️ Назад в профиль")]
            ]
            await update.message.reply_text(
                "Хотите изменить другие данные?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("Пожалуйста, введите корректный возраст (от 1 до 120 лет).")
            return EDIT_AGE
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число для возраста.")
        return EDIT_AGE

async def edit_height_handler(update: Update, context):
    text = update.message.text
    
    menu_buttons = [
        "✏️ Изменить данные", "📊 Детальная статистика", "🎯 Мои цели", "📈 График веса",
        "⬅️ Назад в профиль", "⬅️ Назад в главное меню", "📝 Изменить возраст", 
        "📝 Изменить рост", "📝 Изменить вес", "📋 История изменений", "📝 Изменить еще данные",
        "🍽️ Питание", "👤 Профиль", "📊 Калорийность", "💳 Подписка"
    ]
    
    if text in menu_buttons:
        await update.message.reply_text("❌ Редактирование отменено.")
        if text == "⬅️ Назад в профиль" or text == "✏️ Изменить данные":
            await show_profile(update, context)
        elif text == "⬅️ Назад в главное меню":
            await send_main_menu(update, context)
        elif text in ["📝 Изменить возраст", "📝 Изменить рост", "📝 Изменить вес", "📝 Изменить еще данные"]:
            await edit_profile_start(update, context)
        else:
            await handle_message(update, context)
        context.user_data.pop('current_user_id', None)
        return ConversationHandler.END
    
    try:
        height = float(text)
        if 50 <= height <= 250:
            user_id = context.user_data.get('current_user_id')
            if not user_id:
                await update.message.reply_text("Ошибка: Не могу определить ваш ID.")
                return ConversationHandler.END
            user_data = get_user_data_by_telegram_id(update.effective_user.id)
            if not user_data:
                await update.message.reply_text("Ошибка: Данные пользователя не найдены.")
                return ConversationHandler.END
            _, _, _, _, _, age, current_height, weight, _, _, _ = user_data
            if age and weight:
                bmi = calculate_bmi(height, weight)
                recommendation = get_bmi_recommendation(bmi)
                update_user_profile_data(
                    user_id=user_id,
                    height=height,
                    bmi=bmi,
                    bmi_recommendation=recommendation
                )
                await update.message.reply_text(f"✅ Рост успешно изменен на {height} см.\nВаш ИМТ: {bmi:.1f}")
            else:
                update_user_profile_data(user_id=user_id, height=height)
                await update.message.reply_text(f"✅ Рост успешно изменен на {height} см.")
            keyboard = [
                [KeyboardButton("📝 Изменить еще данные")],
                [KeyboardButton("⬅️ Назад в профиль")]
            ]
            await update.message.reply_text(
                "Хотите изменить другие данные?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("Пожалуйста, введите корректный рост (от 50 до 250 см).")
            return EDIT_HEIGHT
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число для роста.")
        return EDIT_HEIGHT

async def edit_weight_handler(update: Update, context):
    text = update.message.text
    
    menu_buttons = [
        "✏️ Изменить данные", "📊 Детальная статистика", "🎯 Мои цели", "📈 График веса",
        "⬅️ Назад в профиль", "⬅️ Назад в главное меню", "📝 Изменить возраст", 
        "📝 Изменить рост", "📝 Изменить вес", "📋 История изменений", "📝 Изменить еще данные",
        "🍽️ Питание", "👤 Профиль", "📊 Калорийность", "💳 Подписка"
    ]
    
    if text in menu_buttons:
        await update.message.reply_text("❌ Редактирование отменено.")
        if text == "⬅️ Назад в профиль" or text == "✏️ Изменить данные":
            await show_profile(update, context)
        elif text == "⬅️ Назад в главное меню":
            await send_main_menu(update, context)
        elif text in ["📝 Изменить возраст", "📝 Изменить рост", "📝 Изменить вес", "📝 Изменить еще данные"]:
            await edit_profile_start(update, context)
        else:
            await handle_message(update, context)
        context.user_data.pop('current_user_id', None)
        return ConversationHandler.END
    
    try:
        weight = float(text)
        if 20 <= weight <= 300:
            user_id = context.user_data.get('current_user_id')
            if not user_id:
                await update.message.reply_text("Ошибка: Не могу определить ваш ID.")
                return ConversationHandler.END
            user_data = get_user_data_by_telegram_id(update.effective_user.id)
            if not user_data:
                await update.message.reply_text("Ошибка: Данные пользователя не найдены.")
                return ConversationHandler.END
            _, _, _, _, _, age, height, current_weight, _, _, _ = user_data
            if age and height:
                bmi = calculate_bmi(height, weight)
                recommendation = get_bmi_recommendation(bmi)
                update_user_profile_data(
                    user_id=user_id,
                    weight=weight,
                    bmi=bmi,
                    bmi_recommendation=recommendation
                )
                await update.message.reply_text(f"✅ Вес успешно изменен на {weight} кг.\nВаш ИМТ: {bmi:.1f}")
            else:
                update_user_profile_data(user_id=user_id, weight=weight)
                await update.message.reply_text(f"✅ Вес успешно изменен на {weight} кг.")
            add_weight_history(user_id, weight)
            if age and height and current_weight:
                old_bmi = calculate_bmi(height, current_weight)
                new_bmi = calculate_bmi(height, weight)
                weight_diff = weight - current_weight
                bmi_info = f"\n📊 **Изменение ИМТ:**\n"
                bmi_info += f"• Было: {old_bmi:.1f}\n"
                bmi_info += f"• Стало: {new_bmi:.1f}\n"
                bmi_info += f"• Изменение веса: {weight_diff:+.1f} кг\n"
                await update.message.reply_text(bmi_info, parse_mode='Markdown')
            keyboard = [
                [KeyboardButton("📝 Изменить еще данные")],
                [KeyboardButton("⬅️ Назад в профиль")]
            ]
            await update.message.reply_text(
                "Хотите изменить другие данные?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("Пожалуйста, введите корректный вес (от 20 до 300 кг).")
            return EDIT_WEIGHT
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число для веса.")
        return EDIT_WEIGHT

async def update_weight_start(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return ConversationHandler.END
    user_id, _, _, _, _, age, height, current_weight, _, _, _ = user_data
    if current_weight:
        await update.message.reply_text(
            f"📝 **Обновление веса**\n\n"
            f"Текущий вес: {current_weight} кг\n\n"
            f"Введите новый вес (в килограммах):"
        )
    else:
        await update.message.reply_text("Введите ваш вес (в килограммах):")
    context.user_data['current_user_id'] = user_id
    context.user_data['updating_weight'] = True
    return EDIT_WEIGHT

async def show_profile_history(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return
    user_id = user_data[0]
    profile_history = get_profile_history(user_id)
    weight_history = get_weight_history(user_id, limit=5)
    text = "📋 **История изменений профиля**\n\n"
    if profile_history:
        text += "**Последние изменения профиля:**\n"
        for i, (age, height, weight, bmi, change_date, change_type) in enumerate(profile_history[:3], 1):
            try:
                date_str = datetime.strptime(change_date, '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y %H:%M')
            except:
                date_str = change_date
            changes = []
            if age: changes.append(f"Возраст: {age}")
            if height: changes.append(f"Рост: {height} см")
            if weight: changes.append(f"Вес: {weight} кг")
            if bmi: changes.append(f"ИМТ: {bmi:.1f}")
            if changes:
                text += f"{i}. {date_str}: {', '.join(changes)}\n"
    else:
        text += "История изменений профиля пока пуста.\n"
    text += "\n**Последние изменения веса:**\n"
    if weight_history:
        for i, (weight, record_date, change_date) in enumerate(weight_history[:5], 1):
            try:
                date_str = datetime.strptime(record_date, '%Y-%m-%d').strftime('%d.%m.%Y')
            except:
                date_str = record_date
            text += f"{i}. {date_str}: {weight} кг\n"
    else:
        text += "История изменений веса пока пуста.\n"
    keyboard = [[KeyboardButton("⬅️ Назад к редактированию")]]
    await update.message.reply_text(text, parse_mode='Markdown',
                                  reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def show_profile(update: Update, context):
    """Показывает профиль пользователя с графиком веса"""
    logger.info(f"Обработчик show_profile вызван для пользователя {update.effective_user.id}")
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Пожалуйста, заполните свои данные, используя команду /start.")
        return
    
    try:
        user_id, _, username, first_name, last_name, age, height, weight, bmi, bmi_recommendation, reg_date = user_data
        
        # ===== ПОКАЗЫВАЕМ ГРАФИК ВЕСА В ПРОФИЛЕ =====
        chart_image = generate_weight_chart(user_id)
        if chart_image:
            await update.message.reply_photo(
                photo=chart_image,
                caption="📈 **Ваш прогресс изменения веса**\n\n"
                       "• Каждая точка — день измерения\n"
                       "• Линия показывает динамику",
                parse_mode='Markdown'
            )
        
        subscription_status = get_user_subscription_status(user_id)
        progress_stats = get_user_progress_stats(user_id)
        text = f"👤 **Ваш профиль**\n\n"
        text += f"**Основная информация:**\n"
        text += f"• Имя: {first_name or 'Не указано'}\n"
        text += f"• Username: @{username or 'Не указан'}\n"
        text += f"• Возраст: {age if age else '❌ Не заполнено'}\n"
        text += f"• Рост: {height if height else '❌ Не заполнено'} см\n"
        text += f"• Вес: {weight if weight else '❌ Не заполнено'} кг\n\n"
        if all([age, height, weight]):
            text += f"**Показатели здоровья:**\n"
            text += f"• ИМТ: {bmi:.1f} ({get_bmi_category(bmi).capitalize()})\n"
            text += f"• Рекомендация: {bmi_recommendation}\n\n"
        else:
            text += f"**Показатели здоровья:**\n❌ Заполните все данные для расчета\n\n"
        text += f"**Статистика прогресса:**\n"
        if progress_stats['initial_weight'] and progress_stats['current_weight']:
            weight_diff = progress_stats['current_weight'] - progress_stats['initial_weight']
            weight_trend = "📈" if weight_diff > 0 else "📉" if weight_diff < 0 else "➡️"
            text += f"• Начальный вес: {progress_stats['initial_weight']} кг\n"
            text += f"• Текущий вес: {progress_stats['current_weight']} кг\n"
            text += f"• Изменение: {weight_trend} {abs(weight_diff):.1f} кг\n"
        else:
            text += f"• Прогресс: Недостаточно данных\n"
        text += f"• Активных дней: {progress_stats['active_days']}\n\n"
        subscription_emojis = {'free': '🔓', 'week_200': '⭐', 'month_350': '🌟', 'trial': '🎁'}
        sub_display = subscription_status
        if sub_display == 'trial':
            sub_display = 'пробный'
        text += f"**Подписка:** {subscription_emojis.get(subscription_status, '❓')} {sub_display.replace('_', ' ').title()}\n\n"
        if reg_date:
            try:
                reg_date_str = datetime.strptime(reg_date, '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y')
                text += f"📅 Дата регистрации: {reg_date_str}"
            except ValueError:
                text += f"📅 Дата регистрации: {reg_date}"
        keyboard = [
            [KeyboardButton("✏️ Изменить данные"), KeyboardButton("📊 Детальная статистика")],
            [KeyboardButton("🎯 Мои цели"), KeyboardButton("📈 График веса")],
            [KeyboardButton("⬅️ Назад в главное меню")]
        ]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    except Exception as e:
        logger.error(f"Ошибка в show_profile: {e}")
        await update.message.reply_text("Произошла ошибка при загрузке профиля. Попробуйте позже.")

async def show_detailed_stats(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Произошла ошибка при получении данных.")
        return
    user_id = user_data[0]
    weekly_calories, avg_calories = get_weekly_calories(user_id)
    text = "📊 **Детальная статистика**\n\n"
    if weekly_calories:
        text += "**Калории за последние 7 дней:**\n"
        for date_str, calories in weekly_calories[:7]:
            date_formatted = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m')
            text += f"• {date_formatted}: {calories or 0} ккал\n"
    else:
        text += "**Калории:** Нет данных за последние 7 дней\n"
    text += f"\n**Среднее потребление:** {avg_calories:.0f} ккал/день\n"
    if avg_calories:
        if avg_calories < 1500:
            text += "\n💡 Рекомендация: Увеличьте потребление калорий для здорового метаболизма"
        elif avg_calories > 3000:
            text += "\n💡 Рекомендация: Рассмотрите снижение калорий для контроля веса"
        else:
            text += "\n💡 Рекомендация: Отличный баланс калорий!"
    keyboard = [[KeyboardButton("⬅️ Назад в профиль")]]
    await update.message.reply_text(text, parse_mode='Markdown',
                                  reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def show_goals_menu(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Произошла ошибка при получении данных.")
        return
    user_id, _, _, _, _, age, height, weight, bmi, _, _ = user_data
    text = "🎯 **Рекомендуемые нормы калорий**\n\n"
    if all([age, height, weight]):
        if height and weight and age:
            maintenance_calories = calculate_calorie_needs(age, height, weight, "maintenance")
            loss_calories = calculate_calorie_needs(age, height, weight, "weight_loss")
            gain_calories = calculate_calorie_needs(age, height, weight, "weight_gain")
            if maintenance_calories:
                text += f"**Поддержание веса:** {maintenance_calories:.0f} ккал/день\n\n"
            if loss_calories:
                text += f"**Снижение веса:** {loss_calories:.0f} ккал/день\n\n"
            if gain_calories:
                text += f"**Набор массы:** {gain_calories:.0f} ккал/день\n\n"
            if bmi < 18.5:
                text += "💡 **Рекомендация:** У вас недостаточный вес. Рекомендуется цель 'Набор массы'.\n"
            elif bmi > 25:
                text += "💡 **Рекомендация:** У вас избыточный вес. Рекомендуется цель 'Снижение веса'.\n"
            else:
                text += "💡 **Рекомендация:** У вас нормальный вес. Рекомендуется цель 'Поддержание веса'.\n"
        else:
            text += "❌ Недостаточно данных для расчета калорий.\n"
    else:
        text += "❌ Заполните все данные профиля (возраст, рост, вес) для получения рекомендаций.\n"
    keyboard = [[KeyboardButton("⬅️ Назад в профиль")]]
    await update.message.reply_text(text, parse_mode='Markdown',
                                  reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def show_weight_chart_info(update: Update, context):
    """Отображает график и статистику изменения веса."""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return
        
    user_id = user_data[0]
    weight_stats = get_weight_statistics(user_id)
    
    chart_image = generate_weight_chart(user_id)
    
    if chart_image:
        await update.message.reply_photo(
            photo=chart_image, 
            caption="📈 Ваш график изменения веса"
        )
    else:
        await update.message.reply_text("📈 Недостаточно данных для построения графика. Нужно минимум 2 записи.")
    
    text = "📊 **Статистика изменения веса**\n\n"
    if weight_stats:
        text += "**Основные показатели:**\n"
        text += f"• Начальный вес: {weight_stats['first_weight']:.1f} кг ({weight_stats['first_date']})\n"
        text += f"• Текущий вес: {weight_stats['last_weight']:.1f} кг ({weight_stats['last_date']})\n"
        text += f"• Общее изменение: {weight_stats['total_change']:+.1f} кг\n\n"
        text += f"• Минимальный вес: {weight_stats['min_weight']:.1f} кг\n"
        text += f"• Максимальный вес: {weight_stats['max_weight']:.1f} кг\n"
        text += f"• Всего записей: {weight_stats['total_records']}\n"
    else:
        text += "❌ Недостаточно данных для статистики.\n"
    
    keyboard = [
        [KeyboardButton("📝 Обновить вес"), KeyboardButton("📋 История веса")],
        [KeyboardButton("⬅️ Назад в профиль")]
    ]
    await update.message.reply_text(
        text, 
        parse_mode='Markdown', 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def show_weight_history(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return
    user_id = user_data[0]
    weight_history = get_weight_history(user_id, limit=20)
    text = "📋 **Подробная история веса**\n\n"
    if weight_history:
        text += "**Все записи:**\n"
        prev_weight = None
        for weight, record_date, change_date in weight_history:
            date_str = datetime.strptime(record_date, '%Y-%m-%d').strftime('%d.%m.%Y')
            change_str = ""
            if prev_weight is not None:
                change = weight - prev_weight
                if change > 0:
                    change_str = f" 📈 +{change:.1f} кг"
                elif change < 0:
                    change_str = f" 📉 {change:.1f} кг"
                else:
                    change_str = " ➡️ 0 кг"
            text += f"• {date_str}: {weight:.1f} кг{change_str}\n"
            prev_weight = weight
    else:
        text += "История веса пока пуста.\n"
        text += "Обновите свой вес, чтобы начать отслеживать прогресс.\n"
    keyboard = [[KeyboardButton("⬅️ Назад к статистике веса")]]
    await update.message.reply_text(text, parse_mode='Markdown',
                                  reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

def generate_weight_chart(user_id):
    """Генерирует график изменения веса пользователя"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT weight, record_date 
        FROM WeightHistory 
        WHERE user_id = ? 
        ORDER BY record_date ASC
    """, (user_id,))
    weight_data = cursor.fetchall()
    conn.close()

    if not weight_data or len(weight_data) < 2:
        return None

    dates = [datetime.strptime(row[1], '%Y-%m-%d') for row in weight_data]
    weights = [row[0] for row in weight_data]

    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(dates, weights, marker='o', linestyle='-', color='#2E86C1', linewidth=2, markersize=8, markerfacecolor='#E74C3C')
    
    ax.set_xlabel("Дата", fontsize=12, fontweight='bold')
    ax.set_ylabel("Вес (кг)", fontsize=12, fontweight='bold')
    ax.set_title("Динамика изменения веса", fontsize=16, fontweight='bold', pad=20)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()

    for i, (date, weight) in enumerate(zip(dates, weights)):
        if i == 0 or i == len(dates) - 1 or weight == min(weights) or weight == max(weights):
            ax.annotate(f'{weight:.1f}', 
                        (date, weight), 
                        textcoords="offset points",
                        xytext=(0, 15), 
                        ha='center',
                        fontsize=10,
                        fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.3))

    ax.grid(True, linestyle='--', alpha=0.7)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    
    return buf

# --- ПИТАНИЕ И РАЦИОНЫ ---
async def show_nutrition_menu(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    
    # ===== ОТПРАВЛЯЕМ КАРТИНКУ РАЗДЕЛА ПИТАНИЕ =====
    await send_image_if_exists(
        update,
        "images/nutrition.png",
        "🍽️ **Добро пожаловать в раздел питания!**\n\n"
        "Здесь вы можете составить персональный рацион на основе ваших целей."
    )
    
    if user_data:
        user_id = user_data[0]
        subscription_status = get_user_subscription_status(user_id)
        subscription_info = {
            'free': '🔓 Бесплатная версия',
            'week_200': '⭐ Недельная подписка',
            'month_350': '🌟 Месячная подписка',
            'trial': '🎁 Пробный период'
        }.get(subscription_status, '❓ Неизвестно')
        
        menu_text = f"🍽️ **Раздел 'Питание'**\n\n"
        menu_text += f"📊 **Ваш статус:** {subscription_info}\n\n"
        menu_text += "**Доступные функции:**\n"
        menu_text += "• 📅 Составить рацион - персонализированный план питания\n"
        menu_text += "• ℹ️ Моя подписка - информация о текущей подписке\n\n"
        
        if subscription_status == 'free':
            menu_text += "🔓 **Бесплатно доступно:** план на 1 день\n"
            menu_text += "⭐ **С подпиской:** планы на неделю и месяц\n"
        elif subscription_status in ['week_200', 'trial']:
            menu_text += "⭐ **Ваша подписка включает:** план на неделю\n"
            menu_text += "🌟 **Для плана на месяц:** обновите до месячной подписки\n"
        elif subscription_status == 'month_350':
            menu_text += "🌟 **Ваша подписка включает:** планы на неделю и месяц\n"
        
        keyboard = [
            [KeyboardButton("📅 Составить рацион")],
            [KeyboardButton("ℹ️ Моя подписка")],
            [KeyboardButton("⬅️ Назад в главное меню")]
        ]
        await update.message.reply_text(
            menu_text,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        keyboard = [[KeyboardButton("⬅️ Назад в главное меню")]]
        await update.message.reply_text(
            "🍽️ Раздел 'Питание'\n\nЧто вы хотите сделать?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

async def show_my_subscription(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Произошла ошибка: не удалось получить данные вашего пользователя. Попробуйте /start.")
        return
    user_id = user_data[0]
    subscription_status = get_user_subscription_status(user_id)
    subscription_info = {
        'free': 'У вас бесплатный тариф. Для доступа к полному функционалу оформите подписку.',
        'week_200': 'Ваша активная подписка: Недельная (200р).',
        'month_350': 'Ваша активная подписка: Месячная (350р).',
        'trial': '🎁 У вас активен пробный период (1 день).'
    }.get(subscription_status, 'Не удалось определить статус вашей подписки.')
    keyboard = [[KeyboardButton("⬅️ Назад в питание")]]
    await update.message.reply_text(f"**Статус подписки:**\n{subscription_info}",
                                  parse_mode='Markdown',
                                  reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def show_ration_options(update: Update, context):
    user_id = get_user_data_by_telegram_id(update.effective_user.id)[0]
    subscription_type = get_user_subscription_status(user_id)
    buttons = [KeyboardButton("1 день (бесплатно)")]
    if subscription_type in ['week_200', 'month_350', 'trial']:
        buttons.append(KeyboardButton("Неделя (с подпиской)"))
    if subscription_type == 'month_350':
        buttons.append(KeyboardButton("Месяц (с подписки)"))
    keyboard = [buttons, [KeyboardButton("⬅️ Назад в питание")]]
    await update.message.reply_text("Выберите длительность рациона:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return RATION_DURATION

async def choose_ration_goal(update: Update, context):
    selected_duration = update.message.text
    logger.info(f"Выбрана длительность рациона: {selected_duration}")
    
    if selected_duration == "⬅️ Назад в питание":
        await show_nutrition_menu(update, context)
        return ConversationHandler.END
    
    if selected_duration == "⬅️ Назад в главное меню":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    duration_map = {
        "1 день (бесплатно)": "1 день",
        "Неделя (с подпиской)": "неделя",
        "Неделя (с подписки)": "неделя",
        "Месяц (с подписки)": "месяц"
    }
    selected_duration_clean = duration_map.get(selected_duration)
    if not selected_duration_clean:
        await update.message.reply_text("Некорректный выбор длительности. Пожалуйста, выберите из предложенных.")
        return RATION_DURATION
    
    user_id = get_user_data_by_telegram_id(update.effective_user.id)[0]
    subscription_status = get_user_subscription_status(user_id)
    
    if selected_duration_clean == "1 день":
        pass
    elif selected_duration_clean == "неделя":
        if subscription_status == 'free':
            await update.message.reply_text(
                "❌ Для составления плана на неделю нужна подписка.\n\n"
                "Пожалуйста, оформите подписку в разделе '💳 Подписка'."
            )
            await show_nutrition_menu(update, context)
            return ConversationHandler.END
    elif selected_duration_clean == "месяц":
        if subscription_status != 'month_350':
            if subscription_status == 'free':
                message = (
                    "❌ Для составления плана на месяц нужна месячная подписка.\n\n"
                    "У вас: Бесплатная версия ❌\n"
                    "Требуется: Месячная подписка (350р) ✅\n\n"
                    "Пожалуйста, оформите месячную подписку в разделе '💳 Подписка'."
                )
            else:
                message = (
                    "❌ Уровень подписки недостаточен для плана на месяц.\n\n"
                    "У вас: Недельная подписка (200р) ⚠️\n"
                    "Требуется: Месячная подписка (350р) ✅\n\n"
                    "Вы можете:\n"
                    "1. Перейти на месячную подписку в разделе '💳 Подписка'\n"
                    "2. Выбрать план на неделю (доступен с вашей подпиской)"
                )
            await update.message.reply_text(message)
            await show_nutrition_menu(update, context)
            return ConversationHandler.END
    
    context.user_data['selected_ration_duration'] = selected_duration_clean
    context.user_data['selected_duration_display'] = selected_duration
    
    keyboard = [
        [KeyboardButton("💪 Набор массы")],
        [KeyboardButton("⚖️ Поддержание веса")],
        [KeyboardButton("📉 Диета (похудение)")],
        [KeyboardButton("⬅️ Назад в питание")]
    ]
    await update.message.reply_text(
        f"Вы выбрали: {selected_duration}\n\n"
        "Теперь выберите цель вашего рациона:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return RATION_GOAL

def parse_ration_response(response_text, duration):
    """Парсит ответ GigaChat и разбивает на части."""
    parts = []
    lines = response_text.split('\n')
    
    if duration == "неделя":
        days = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]
        current_day = None
        current_content = []
        extra_content = []
        
        in_extra = False
        for line in lines:
            upper_line = line.strip().upper()
            
            day_found = None
            for day in days:
                if upper_line.startswith(f"**{day}**") or upper_line.startswith(day):
                    day_found = day.capitalize()
                    break
            
            if day_found:
                if current_day:
                    parts.append({
                        'title': current_day,
                        'content': '\n'.join(current_content).strip()
                    })
                current_day = day_found
                current_content = []
                in_extra = False
                continue
            
            if any(marker in upper_line for marker in ["🍳 ТОП", "💡 СОВЕТ", "**🍳", "**💡"]):
                in_extra = True
            
            if current_day and not in_extra:
                current_content.append(line)
            elif in_extra:
                extra_content.append(line)
        
        if current_day:
            parts.append({
                'title': current_day,
                'content': '\n'.join(current_content).strip()
            })
        
        if extra_content:
            parts.append({
                'title': 'Советы и рецепты',
                'content': '\n'.join(extra_content).strip()
            })
    
    elif duration == "месяц":
        weeks = ["НЕДЕЛЯ 1", "НЕДЕЛЯ 2", "НЕДЕЛЯ 3", "НЕДЕЛЯ 4"]
        current_week = None
        current_content = []
        
        for line in lines:
            upper_line = line.strip().upper()
            
            week_found = None
            for i, week in enumerate(weeks):
                if week in upper_line:
                    week_found = f"Неделя {i+1}"
                    break
            
            if week_found:
                if current_week:
                    parts.append({
                        'title': current_week,
                        'content': '\n'.join(current_content).strip()
                    })
                current_week = week_found
                current_content = [line]
                continue
            
            if current_week:
                current_content.append(line)
        
        if current_week:
            parts.append({
                'title': current_week,
                'content': '\n'.join(current_content).strip()
            })
        
        extra_started = False
        extra_content = []
        for line in lines:
            upper = line.strip().upper()
            if any(marker in upper for marker in ["📦 СПИСОК", "🍳 7 ЛУЧШИХ", "💡 СОВЕТ"]):
                extra_started = True
            if extra_started:
                extra_content.append(line)
        
        if extra_content:
            parts.append({
                'title': 'Полезная информация',
                'content': '\n'.join(extra_content).strip()
            })
    
    else:
        parts.append({
            'title': 'Ваш дневной рацион',
            'content': response_text.strip()
        })
    
    return parts

async def show_ration_part(update: Update, context, part_index=None):
    """Показывает часть рациона с кнопками навигации"""
    parts = context.user_data.get('ration_parts', [])
    
    if not parts:
        await update.message.reply_text("❌ Ошибка: рацион не найден.")
        return ConversationHandler.END
    
    if part_index is None:
        part_index = context.user_data.get('current_ration_part', 0)
    else:
        context.user_data['current_ration_part'] = part_index
    
    total_parts = len(parts)
    current_part = parts[part_index]
    
    duration = context.user_data.get('ration_duration', '')
    period_word = "день" if duration == "неделя" else "неделя" if duration == "месяц" else "день"
    
    header = f"📋 **{current_part['title']}** ({part_index + 1}/{total_parts} {period_word})\n\n"
    message = header + current_part['content']
    
    if len(message) > 4000:
        message = message[:3997] + "..."
    
    keyboard = []
    nav_buttons = []
    
    if part_index > 0:
        nav_buttons.append("◀️ Назад")
    if part_index < total_parts - 1:
        nav_buttons.append("Вперед ▶️")
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    second_row = []
    second_row.append("📋 Показать всё текстом")
    second_row.append("📅 Новый рацион")
    keyboard.append(second_row)
    
    keyboard.append(["⬅️ Назад в главное меню"])
    
    try:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    except:
        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    
    return NAVIGATE_RATION

async def navigate_ration(update: Update, context):
    """Обработчик навигации по рациону"""
    text = update.message.text
    parts = context.user_data.get('ration_parts', [])
    current_idx = context.user_data.get('current_ration_part', 0)
    total_parts = len(parts)
    
    if text == "◀️ Назад":
        new_idx = max(0, current_idx - 1)
        return await show_ration_part(update, context, new_idx)
    
    elif text == "Вперед ▶️":
        new_idx = min(total_parts - 1, current_idx + 1)
        return await show_ration_part(update, context, new_idx)
    
    elif text == "📋 Показать всё текстом":
        full_text = context.user_data.get('full_response', '')
        
        for i in range(0, len(full_text), 4000):
            chunk = full_text[i:i+4000]
            try:
                await update.message.reply_text(chunk, parse_mode='Markdown')
            except:
                await update.message.reply_text(chunk)
        
        keyboard = []
        nav_buttons = []
        if current_idx > 0:
            nav_buttons.append("◀️ Назад")
        if current_idx < total_parts - 1:
            nav_buttons.append("Вперед ▶️")
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append(["📋 Показать всё текстом", "📅 Новый рацион"])
        keyboard.append(["⬅️ Назад в главное меню"])
        
        await update.message.reply_text(
            f"📋 Полный рацион показан выше. Текущая позиция: {current_idx + 1}/{total_parts}",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return NAVIGATE_RATION
    
    elif text == "📅 Новый рацион":
        context.user_data.pop('ration_parts', None)
        context.user_data.pop('current_ration_part', None)
        context.user_data.pop('full_response', None)
        context.user_data.pop('ration_duration', None)
        return await show_ration_options(update, context)
    
    elif text == "⬅️ Назад в питание":
        context.user_data.pop('ration_parts', None)
        context.user_data.pop('current_ration_part', None)
        context.user_data.pop('full_response', None)
        context.user_data.pop('ration_duration', None)
        await show_nutrition_menu(update, context)
        return ConversationHandler.END
    
    elif text == "⬅️ Назад в главное меню":
        context.user_data.pop('ration_parts', None)
        context.user_data.pop('current_ration_part', None)
        context.user_data.pop('full_response', None)
        context.user_data.pop('ration_duration', None)
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    return NAVIGATE_RATION

async def get_ration_from_giga(update: Update, context):
    selected_goal = update.message.text
    
    if selected_goal == "⬅️ Назад в питание":
        await show_nutrition_menu(update, context)
        return ConversationHandler.END
    
    if selected_goal == "⬅️ Назад в главное меню":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    selected_duration = context.user_data.get('selected_ration_duration')
    if not selected_duration:
        await update.message.reply_text("Ошибка: не выбрана длительность рациона. Попробуйте сначала.")
        await show_nutrition_menu(update, context)
        return ConversationHandler.END
    
    loading_message = await update.message.reply_text(
        "⏳ Обращаюсь к GigaChat для составления персонального рациона...\n"
        "Это может занять 15-30 секунд."
    )
    
    user_data_full = get_user_data_by_telegram_id(update.effective_user.id)
    if not user_data_full:
        await update.message.reply_text("Ошибка: Данные пользователя не найдены.")
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    user_id, _, _, _, _, age, height, weight, bmi, bmi_recommendation, _ = user_data_full
    bmi_category = get_bmi_category(bmi)
    
    goal_map = {
        "💪 Набор массы": "набор мышечной массы",
        "⚖️ Поддержание веса": "поддержание текущего веса",
        "📉 Диета (похудение)": "снижение веса"
    }
    goal_clean = goal_map.get(selected_goal, selected_goal)
    
    # Расчет калорий
    if all([age, height, weight]):
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
        if goal_clean == "снижение веса":
            daily_calories = int(bmr * 1.2 - 400)
            protein_pct, fat_pct, carb_pct = 0.35, 0.25, 0.40
        elif goal_clean == "набор мышечной массы":
            daily_calories = int(bmr * 1.55 + 300)
            protein_pct, fat_pct, carb_pct = 0.30, 0.25, 0.45
        else:
            daily_calories = int(bmr * 1.375)
            protein_pct, fat_pct, carb_pct = 0.25, 0.30, 0.45
        
        daily_protein = int(daily_calories * protein_pct / 4)
        daily_fat = int(daily_calories * fat_pct / 9)
        daily_carbs = int(daily_calories * carb_pct / 4)
    else:
        daily_calories, daily_protein, daily_fat, daily_carbs = 2500, 150, 70, 300

    # ПРОМПТЫ ДЛЯ GigaChat (оставлены как в оригинале)
    if selected_duration == "1 день":
        prompt = f"""Создай подробный план питания на 1 день.

👤 ДАННЫЕ КЛИЕНТА:
• Возраст: {age} лет • Рост: {height} см • Вес: {weight} кг
• ИМТ: {bmi} ({bmi_category})
• Цель: {goal_clean}
• Суточная норма: {daily_calories} ккал (Б: {daily_protein}г, Ж: {daily_fat}г, У: {daily_carbs}г)

📋 ОТВЕТ ДАЙ В ФОРМАТЕ:

**🍳 ЗАВТРАК** (~{int(daily_calories * 0.25)} ккал)
• Блюдо: [название]
• Состав: [основные ингредиенты с граммовками]
• КБЖУ: [ккал] | Б: [г] | Ж: [г] | У: [г]
• Рецепт: [1-2 предложения как готовить]

**🍲 ОБЕД** (~{int(daily_calories * 0.35)} ккал)
[такой же формат]

**🍱 УЖИН** (~{int(daily_calories * 0.25)} ккал)
[такой же формат]

**🍎 ПЕРЕКУС** (~{int(daily_calories * 0.15)} ккал)
[такой же формат]

**💡 3 СОВЕТА НА ДЕНЬ:**
• Конкретные рекомендации под цель «{goal_clean}»

**📊 ИТОГО:** Ккал: ХХХ | Б: ХХг | Ж: ХХг | У: ХХг

ВАЖНО:
• Только доступные продукты (гречка, курица, творог, яйца, рыба, овощи, овсянка)
• Простые рецепты
• Строго соблюдай формат
• Русский язык"""

    elif selected_duration == "неделя":
        prompt = f"""Создай план питания на 7 дней. Каждый день оформляй по шаблону и разделяй маркером [SEPARATOR].

👤 Клиент: {age} лет, {height} см, {weight} кг, ИМТ {bmi} ({bmi_category})
🎯 Цель: {goal_clean}
📊 Норма: {daily_calories} ккал/день (Б:{daily_protein}г Ж:{daily_fat}г У:{daily_carbs}г)

⚠️ ФОРМАТ (используй [SEPARATOR] между днями):

**🍽️ День 1 — ПОНЕДЕЛЬНИК**
• Завтрак: [блюдо, основные ингредиенты] | ~{int(daily_calories * 0.25)} ккал
• Обед: [блюдо, основные ингредиенты] | ~{int(daily_calories * 0.35)} ккал
• Ужин: [блюдо, основные ингредиенты] | ~{int(daily_calories * 0.25)} ккал
• Перекус: [блюдо, основные ингредиенты] | ~{int(daily_calories * 0.15)} ккал

[SEPARATOR]

**🍽️ День 2 — ВТОРНИК**
[новые блюда, не повторять ПН]
...

[SEPARATOR]

**🍽️ День 3 — СРЕДА**
[блюда на основе рыбы/морепродуктов]

[SEPARATOR]

**🍽️ День 4 — ЧЕТВЕРГ**
[блюда на основе птицы]

[SEPARATOR]

**🍽️ День 5 — ПЯТНИЦА**
[блюда на основе мяса]

[SEPARATOR]

**🍽️ День 6 — СУББОТА**
[свободный день, интересные блюда]

[SEPARATOR]

**🍽️ День 7 — ВОСКРЕСЕНЬЕ**
[особое меню выходного дня]

[SEPARATOR]

**📋 ДОПОЛНИТЕЛЬНО:**
• ТОП-3 лучших рецепта недели с КБЖУ
• Советы по закупке продуктов на неделю

ПРАВИЛА:
1. Каждый день — ПОЛНОСТЬЮ РАЗНЫЕ блюда
2. Чередуй белки: курица → рыба → говядина → яйца → творог → индейка → баранина
3. 4 приема пищи каждый день
4. Только доступные продукты
5. Укладывайся в {daily_calories}±200 ккал/день
6. СТРОГО используй [SEPARATOR] между днями
7. Русский язык"""

    else:  # месяц
        prompt = f"""Создай план питания на 4 НЕДЕЛИ. Каждую неделю оформляй по шаблону и разделяй маркером [SEPARATOR].

👤 Клиент: {age} лет, {height} см, {weight} кг, ИМТ {bmi} ({bmi_category})
🎯 Цель: {goal_clean}
📊 Норма: {daily_calories} ккал/день (Б:{daily_protein}г Ж:{daily_fat}г У:{daily_carbs}г)

⚠️ ФОРМАТ (используй [SEPARATOR] между неделями, каждая неделя ~15-20 строк):

**🗓️ НЕДЕЛЯ 1 — АДАПТАЦИЯ**
🥣 Завтраки: [3 варианта на неделю с чередованием]
🍛 Обеды: [3-4 варианта]
🥘 Ужины: [2-3 варианта]
🥜 Перекусы: [2-3 варианта]
💡 Совет недели: [1 рекомендация]

[SEPARATOR]

**🗓️ НЕДЕЛЯ 2 — РАЗНООБРАЗИЕ**
🥣 Завтраки: [замени 2 варианта из недели 1]
🍛 Обеды: [замени 2 варианта + добавь новый источник белка]
🥘 Ужины: [замени 1-2 варианта]
🥜 Перекусы: [2 новых варианта]
💡 Совет недели: [1 рекомендация]

[SEPARATOR]

**🗓️ НЕДЕЛЯ 3 — ЗАКРЕПЛЕНИЕ**
🥣 Завтраки: [комбинируй лучшее из недель 1-2 + 1 новый]
🍛 Обеды: [3-4 блюда, основа — разные гарниры]
🥘 Ужины: [2-3 легких варианта]
🥜 Перекусы: [2-3 варианта]
💡 Совет недели: [1 рекомендация]

[SEPARATOR]

**🗓️ НЕДЕЛЯ 4 — ФИНАЛ**
🥣 Завтраки: [топ-варианты из всего месяца]
🍛 Обеды: [3 лучших блюда]
🥘 Ужины: [2-3 варианта]
🥜 Перекусы: [2 варианта]
💡 Совет недели: [1 рекомендация]

[SEPARATOR]

**📦 ПРОДУКТЫ НА МЕСЯЦ** (по категориям, только основное)
**🍳 3 ЛУЧШИХ РЕЦЕПТА МЕСЯЦА** (с КБЖУ)
**💡 5 ГЛАВНЫХ СОВЕТОВ ПРИ «{goal_clean}»**

ПРАВИЛА:
1. Чередование белков: курица→рыба→говядина→яйца→творог→индейка→морепродукты
2. Разные гарниры: гречка→рис→булгур→картофель→макароны→перловка→киноа
3. Сезонные овощи каждый день
4. КАЖДАЯ НЕДЕЛЯ ~15-20 СТРОК (не больше!)
5. Укладывайся в {daily_calories}±200 ккал/день
6. СТРОГО используй [SEPARATOR] между неделями
7. Русский язык"""

    try:
        await loading_message.edit_text("🧠 GigaChat создает ваш персональный рацион...")
        giga_response = await ask_giga_chat(prompt)
        await loading_message.delete()
        
        giga_response = giga_response.strip()
        
        header = f"🍽️ **Ваш рацион на {selected_duration}**\n\n"
        header += f"👤 Возраст: {age} | Рост: {height} см | Вес: {weight} кг\n"
        header += f"🎯 Цель: {goal_clean} | ~{daily_calories} ккал/день\n\n"
        
        if "[SEPARATOR]" in giga_response and selected_duration in ["неделя", "месяц"]:
            parts_raw = giga_response.split("[SEPARATOR]")
            parts = []
            
            for part in parts_raw:
                part = part.strip()
                if not part:
                    continue
                
                lines = part.split('\n')
                title = "Раздел"
                for line in lines[:3]:
                    clean = line.strip()
                    for char in ['#', '*', '`', '_', '~', '•', '📋', '🍽️', '🗓️']:
                        clean = clean.replace(char, '')
                    clean = clean.strip()
                    if clean and len(clean) < 80 and len(clean) > 3:
                        title = clean
                        break
                
                parts.append({
                    'title': title,
                    'content': part
                })
            
            if len(parts) >= 2:
                context.user_data['ration_parts'] = parts
                context.user_data['current_ration_part'] = 0
                context.user_data['full_response'] = header + giga_response
                context.user_data['ration_duration'] = selected_duration
                
                return await show_ration_part(update, context, 0)
        
        full_text = header + giga_response
        
        if len(full_text) > 4000:
            parts = []
            for i in range(0, len(full_text), 3900):
                parts.append(full_text[i:i+3900])
            
            for i, part in enumerate(parts):
                try:
                    await update.message.reply_text(part, parse_mode='Markdown')
                except:
                    await update.message.reply_text(part)
        else:
            try:
                await update.message.reply_text(full_text, parse_mode='Markdown')
            except:
                await update.message.reply_text(full_text)
        
        keyboard = [
            [KeyboardButton("📅 Составить еще рацион")],
            [KeyboardButton("⬅️ Назад в главное меню")]
        ]
        await update.message.reply_text(
            "✅ Рацион готов! Что делаем дальше?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации рациона: {e}")
        await loading_message.edit_text(
            "❌ Произошла ошибка при генерации рациона.\n\n"
            "Попробуйте еще раз через минуту."
        )
    
    context.user_data.pop('selected_ration_duration', None)
    context.user_data.pop('selected_duration_display', None)
    
    return ConversationHandler.END

# =====================================================================
# 6. ПОДПИСКА И ОПЛАТА
# =====================================================================

async def show_week_payment(update: Update, context):
    """Инструкция для оплаты недельной подписки (200₽)."""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Сначала /start")
        return
    user_id = user_data[0]
    text = f"""💳 ОФОРМЛЕНИЕ НЕДЕЛЬНОЙ ПОДПИСКИ

━━━━━━━━━━━━━━━━━━━━━
🎫 ВАШ НОМЕР: {user_id}
━━━━━━━━━━━━━━━━━━━━━

📌 ЧТО ДЕЛАТЬ:

1️⃣ Перейдите по ссылке:
   {PAYMENT_LINK}

2️⃣ Укажите сумму: 200₽

3️⃣ В КОММЕНТАРИИ К ПЕРЕВОДУ
   НАПИШИТЕ ТОЛЬКО ЦИФРЫ: {user_id}

━━━━━━━━━━━━━━━━━━━━━
✅ ПОСЛЕ ОПЛАТЫ: подписка активируется в течение часа
━━━━━━━━━━━━━━━━━━━━━
"""
    try:
        with open('qr.png', 'rb') as qr:
            await update.message.reply_photo(photo=qr, caption=text)
    except FileNotFoundError:
        await update.message.reply_text(text)

async def show_month_payment(update: Update, context):
    """Инструкция для оплаты месячной подписки (350₽)."""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Сначала /start")
        return
    user_id = user_data[0]
    text = f"""💳 ОФОРМЛЕНИЕ МЕСЯЧНОЙ ПОДПИСКИ

━━━━━━━━━━━━━━━━━━━━━
🎫 ВАШ НОМЕР: {user_id}
━━━━━━━━━━━━━━━━━━━━━

📌 ЧТО ДЕЛАТЬ:

1️⃣ Перейдите по ссылке:
   {PAYMENT_LINK}

2️⃣ Укажите сумму: 350₽

3️⃣ В КОММЕНТАРИИ К ПЕРЕВОДУ
   НАПИШИТЕ ТОЛЬКО ЦИФРЫ: {user_id}

━━━━━━━━━━━━━━━━━━━━━
✅ ПОСЛЕ ОПЛАТЫ: подписка активируется в течение часа
━━━━━━━━━━━━━━━━━━━━━
"""
    try:
        with open('qr.png', 'rb') as qr:
            await update.message.reply_photo(photo=qr, caption=text)
    except FileNotFoundError:
        await update.message.reply_text(text)

async def trial_subscription(update: Update, context):
    """Активирует пробный период на 1 день."""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Сначала заполните профиль через /start")
        return
    user_id = user_data[0]
    if activate_trial(user_id):
        await update.message.reply_text(
            "🎁 **Пробный период активирован!**\n\n"
            "✅ Теперь у вас есть доступ ко всем функциям на 1 день.\n"
            "Приятного аппетита! 🍽️",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Вы уже использовали пробный период.\n"
            "Оформите платную подписку, чтобы продолжить.",
            parse_mode='Markdown'
        )

async def show_subscription_menu(update: Update, context):
    """Главное меню подписки."""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: пользователь не найден. /start")
        return ConversationHandler.END
    
    user_id = user_data[0]
    subscription_status = get_user_subscription_status(user_id)
    
    status_text = {
        'free': '🔓 Бесплатный аккаунт',
        'week_200': '⭐ Недельная подписка',
        'month_350': '🌟 Месячная подписка',
        'trial': '🎁 Пробный период'
    }.get(subscription_status, '❓ Неизвестно')
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id_subscription FROM Subscriptions WHERE user_id = ? AND type_subscription_id = 4", (user_id,))
    trial_used = cursor.fetchone() is not None
    conn.close()
    
    keyboard = []
    if not trial_used and subscription_status != 'trial':
        keyboard.append([KeyboardButton("🎁 Пробный день (бесплатно)")])
    keyboard.append([KeyboardButton("📅 Неделя 200₽"), KeyboardButton("📆 Месяц 350₽")])
    keyboard.append([KeyboardButton("⬅️ Назад в главное меню")])
    
    await update.message.reply_text(
        f"💳 **ПОДПИСКА И ОПЛАТА**\n\n"
        f"📊 **Ваш статус:** {status_text}\n\n"
        f"🎫 **Ваш номер для оплаты:** `{user_id}`\n\n"
        f"Выберите действие:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SUBSCRIPTION_MENU_CHOICE

async def handle_subscription_choice(update: Update, context):
    """Обработчик кнопок в меню подписки."""
    text = update.message.text
    logger.info(f"Подписка: нажата кнопка '{text}'")
    
    user_data = get_user_data_by_telegram_id(update.effective_user.id)
    if not user_data:
        await update.message.reply_text("Ошибка: пользователь не найден")
        return ConversationHandler.END
    
    user_id = user_data[0]
    
    if text == "⬅️ Назад в главное меню":
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    elif text == "🎁 Пробный день (бесплатно)":
        await trial_subscription(update, context)
        return await show_subscription_menu(update, context)
    
    elif "Неделя" in text and "200" in text:
        await show_week_payment(update, context)
        return SUBSCRIPTION_MENU_CHOICE
    
    elif "Месяц" in text and "350" in text:
        await show_month_payment(update, context)
        return SUBSCRIPTION_MENU_CHOICE
    
    else:
        await update.message.reply_text("Пожалуйста, выберите опцию из меню.")
        return SUBSCRIPTION_MENU_CHOICE

# =====================================================================
# 7. АДМИН-ПАНЕЛЬ
# =====================================================================

async def admin_command(update: Update, context):
    """Вход в админ-панель по команде /admin"""
    await update.message.reply_text("🔐 Введите логин администратора:")
    return ADMIN_LOGIN

async def admin_login_handler(update: Update, context):
    username = update.message.text
    print(f"🔥 ВВЕДЕН ЛОГИН: '{username}'")
    print(f"🔥 ОЖИДАЕТСЯ ЛОГИН: '{ADMIN_USERNAME}'")
    if username == ADMIN_USERNAME:
        await update.message.reply_text("✅ Логин верный. Теперь введите пароль:")
        return ADMIN_PASSWORD_STATE
    else:
        await update.message.reply_text("❌ Неверный логин. Доступ запрещен.")
        return ConversationHandler.END

async def admin_password_handler(update: Update, context):
    password = update.message.text
    print(f"🔥 ВВЕДЕН ПАРОЛЬ: '{password}'")
    print(f"🔥 ОЖИДАЕТСЯ ПАРОЛЬ: '{ADMIN_PASSWORD}'")
    if password == ADMIN_PASSWORD:
        await update.message.reply_text("✅ Авторизация успешна! Загружаю данные...")
        
        text = f"""👨‍💼 АДМИН-ПАНЕЛЬ УПРАВЛЕНИЯ

📊 Выберите действие:

🔍 1. Поиск пользователя по номеру — введите user_id из комментария
📋 2. Список всех пользователей — просмотр с пагинацией
📥 3. CSV отчет — выгрузка всей базы
━━━━━━━━━━━━━━━━━━━━━
🔐 Ваш логин: {ADMIN_USERNAME}
🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        keyboard = [
            [KeyboardButton("🔍 Поиск пользователя по номеру")],
            [KeyboardButton("📋 Список всех пользователей")],
            [KeyboardButton("📥 Скачать CSV файл")],
            [KeyboardButton("⬅️ Выйти из админ-панели")]
        ]
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADMIN_MENU
    else:
        await update.message.reply_text("❌ Неверный пароль. Доступ запрещен.")
        return ConversationHandler.END

async def admin_menu_handler(update: Update, context):
    """Главное меню админки."""
    text = f"""👨‍💼 АДМИН-ПАНЕЛЬ УПРАВЛЕНИЯ

📊 Выберите действие:

🔍 1. Поиск пользователя по номеру — введите user_id из комментария
📋 2. Список всех пользователей — просмотр с пагинацией
📥 3. CSV отчет — выгрузка всей базы
━━━━━━━━━━━━━━━━━━━━━
🔐 Ваш логин: {ADMIN_USERNAME}
🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
    keyboard = [
        [KeyboardButton("🔍 Поиск пользователя по номеру")],
        [KeyboardButton("📋 Список всех пользователей")],
        [KeyboardButton("📥 Скачать CSV файл")],
        [KeyboardButton("⬅️ Выйти из админ-панели")]
    ]
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

async def admin_search_by_number_start(update: Update, context):
    """Начало поиска пользователя по номеру"""
    context.user_data.pop('admin_selected_user', None)
    
    keyboard = [
        [KeyboardButton("⬅️ Назад в админ-меню")]
    ]
    
    await update.message.reply_text(
        "🔍 Введите номер пользователя\n\n"
        "Номер можно узнать:\n"
        "• Из комментария к платежу\n"
        "• Из списка всех пользователей\n\n"
        "Пример: 1, 2, 3...",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_SEARCH_USER

async def admin_show_user_by_number(update: Update, context):
    """Показывает данные пользователя по номеру"""
    if update.message.text == "⬅️ Назад в админ-меню":
        return await admin_menu_handler(update, context)
    
    try:
        user_number = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Номер должен быть числом! Попробуйте еще раз:")
        return ADMIN_SEARCH_USER
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT
            u.user_id,
            u.telegram_id,
            u.username,
            u.first_name,
            u.last_name,
            u.age,
            u.height,
            u.weight,
            u.bmi,
            u.bmi_recommendation,
            u.registration_date,
            s.id_subscription,
            ts.name as sub_type,
            s.start_date,
            s.end_date,
            s.active
        FROM Users u
        LEFT JOIN Subscriptions s ON u.user_id = s.user_id
            AND s.active = 1
            AND s.end_date > datetime('now')
        LEFT JOIN type_subscriptions ts ON s.type_subscription_id = ts.id_type_subscription
        WHERE u.user_id = ?
        ORDER BY s.end_date DESC
        LIMIT 1
    """, (user_number,))
    
    user = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM Users")
    total_users = cursor.fetchone()[0]
    
    conn.close()
    
    if not user:
        await update.message.reply_text(
            f"❌ Пользователь с номером {user_number} не найден!\n\n"
            f"Доступные номера: от 1 до {total_users}\n"
            f"Всего пользователей в базе: {total_users}\n\n"
            "Введите другой номер или нажмите кнопку 'Назад'"
        )
        return ADMIN_SEARCH_USER
    
    (user_id, telegram_id, username, first_name, last_name,
     age, height, weight, bmi, bmi_rec, reg_date,
     sub_id, sub_type, start_date, end_date, active) = user
    
    context.user_data['admin_selected_user'] = {
        'user_id': user_id,
        'telegram_id': telegram_id,
        'user_number': user_number,
        'username': username,
        'first_name': first_name
    }
    
    try:
        reg_date_obj = datetime.strptime(reg_date, '%Y-%m-%d %H:%M:%S.%f')
        reg_date_str = reg_date_obj.strftime('%d.%m.%Y')
    except:
        reg_date_str = reg_date
    
    if active and end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S.%f')
            days_left = (end_date_obj - datetime.now()).days
            sub_status = f"✅ АКТИВНА\n   • Тип: {sub_type}\n   • Действует до: {end_date_obj.strftime('%d.%m.%Y')}\n   • Осталось дней: {days_left}"
        except:
            sub_status = f"✅ АКТИВНА (до {end_date})"
    else:
        sub_status = "❌ НЕТ АКТИВНОЙ ПОДПИСКИ"
    
    text = f"""📋 ДАННЫЕ ПОЛЬЗОВАТЕЛЯ #{user_id}

━━━━━━━━━━━━━━━━━━━━━

👤 ЛИЧНЫЕ ДАННЫЕ:
• Порядковый номер: {user_id}
• Telegram ID: {telegram_id}
• Username: @{username or 'не указан'}
• Имя: {first_name or 'не указано'} {last_name or ''}
• Дата регистрации: {reg_date_str}

📊 ФИЗИЧЕСКИЕ ПОКАЗАТЕЛИ:
• Возраст: {age if age else '❌ не указан'} лет
• Рост: {height if height else '❌ не указан'} см
• Вес: {weight if weight else '❌ не указан'} кг
• ИМТ: {bmi if bmi else '❌ не рассчитан'}

💎 СТАТУС ПОДПИСКИ:
{sub_status}

━━━━━━━━━━━━━━━━━━━━━
🎫 НОМЕР ДЛЯ ОПЛАТЫ: {user_id}
"""
    
    keyboard = []
    if active:
        keyboard.append([KeyboardButton(f"❌ Отключить подписку (user #{user_id})")])
    else:
        keyboard.append([
            KeyboardButton(f"📅 Неделя 200₽ (user #{user_id})"),
            KeyboardButton(f"📆 Месяц 350₽ (user #{user_id})")
        ])
    keyboard.append([KeyboardButton("🔍 Найти другого пользователя")])
    keyboard.append([KeyboardButton("⬅️ Назад в админ-меню")])
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_USER_CONTROL

async def admin_handle_subscription_action(update: Update, context):
    """Обработка действий с подпиской"""
    text = update.message.text
    user_data = context.user_data.get('admin_selected_user')
    
    if not user_data:
        await update.message.reply_text("❌ Ошибка: выберите пользователя сначала")
        return ADMIN_MENU
    
    user_id = user_data['user_id']
    telegram_id = user_data['telegram_id']
    user_number = user_data['user_number']
    username = user_data['username'] or user_data['first_name'] or f"#{user_number}"
    
    if text == "🔍 Найти другого пользователя":
        context.user_data.pop('admin_selected_user', None)
        return await admin_search_by_number_start(update, context)
    
    if text == "⬅️ Назад в админ-меню":
        context.user_data.pop('admin_selected_user', None)
        return await admin_menu_handler(update, context)
    
    if "Отключить подписку" in text:
        if deactivate_subscription(user_id):
            await update.message.reply_text(
                f"✅ Подписка отключена\n"
                f"Пользователь: #{user_number} (@{username})"
            )
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text="⚠️ Ваша подписка была отключена администратором.\n\n"
                         "По вопросам: @Loony221"
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка при отключении подписки")
    
    elif "Неделя" in text:
        if activate_subscription(user_id, 'Weekly 200', 7):
            await update.message.reply_text(
                f"✅ Недельная подписка выдана!\n"
                f"Пользователь: #{user_number} (@{username})\n"
                f"Сумма: 200₽\n"
                f"Срок: 7 дней"
            )
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text="""🎉 Подписка активирована!

✅ Тариф: Недельный (200₽)
📅 Срок: 7 дней

Теперь вам доступны:
• Персональный рацион на неделю
• Расширенная статистика
• Приоритетная генерация

Приятного аппетита! 🍽️"""
                )
            except:
                await update.message.reply_text("⚠️ Пользователь не уведомлен")
        else:
            await update.message.reply_text("❌ Ошибка при выдаче подписки")
    
    elif "Месяц" in text:
        if activate_subscription(user_id, 'Monthly 350', 30):
            await update.message.reply_text(
                f"✅ Месячная подписка выдана!\n"
                f"Пользователь: #{user_number} (@{username})\n"
                f"Сумма: 350₽\n"
                f"Срок: 30 дней"
            )
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text="""🎉 Подписка активирована!

✅ Тариф: Месячный (350₽)
📅 Срок: 30 дней

Теперь вам доступны:
• Персональный рацион на месяц
• Расширенная статистика
• Приоритетная генерация
• Все премиум-функции

Приятного аппетита! 🍽️"""
                )
            except:
                await update.message.reply_text("⚠️ Пользователь не уведомлен")
        else:
            await update.message.reply_text("❌ Ошибка при выдаче подписки")
    
    update.message.text = str(user_number)
    return await admin_show_user_by_number(update, context)

async def admin_show_all_users_list(update: Update, context):
    """Показывает список всех пользователей"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            CASE
                WHEN s.active = 1 AND s.end_date > datetime('now')
                THEN '✅'
                ELSE '❌'
            END as sub_status,
            COALESCE(ts.name, 'Нет') as sub_type
        FROM Users u
        LEFT JOIN Subscriptions s ON u.user_id = s.user_id
            AND s.active = 1 AND s.end_date > datetime('now')
        LEFT JOIN type_subscriptions ts ON s.type_subscription_id = ts.id_type_subscription
        ORDER BY u.user_id
    """)
    all_users = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM Users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Users WHERE age IS NOT NULL AND height IS NOT NULL AND weight IS NOT NULL")
    users_with_profile = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) FROM Subscriptions 
        WHERE active = 1 AND end_date > datetime('now')
    """)
    active_subscriptions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM CalorieLog")
    total_calorie_entries = cursor.fetchone()[0]
    
    conn.close()
    
    page = context.user_data.get('admin_users_page', 0)
    users_per_page = 10
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    total_pages = (len(all_users) + users_per_page - 1) // users_per_page
    users_on_page = all_users[start_idx:end_idx]
    
    text = f"""📊 АДМИН-ПАНЕЛЬ - СТАТИСТИКА

👥 Пользователи:
• Всего пользователей: {total_users}
• С заполненным профилем: {users_with_profile}
• С активными подписками: {active_subscriptions}

📈 Активность:
• Всего записей калорий: {total_calorie_entries}

📋 СПИСОК ПОЛЬЗОВАТЕЛЕЙ (стр. {page + 1}/{total_pages})
━━━━━━━━━━━━━━━━━━━━━
"""
    
    for user in users_on_page:
        user_id, username, first_name, last_name, status, sub_type = user
        name = first_name or username or f"ID{user_id}"
        if len(name) > 20:
            name = name[:17] + "..."
        text += f"#{user_id:>4} {status} {name} | {sub_type}\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━"
    
    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(KeyboardButton("⬅️ Предыдущая"))
    if page < total_pages - 1:
        nav_row.append(KeyboardButton("➡️ Следующая"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([KeyboardButton("🔍 Поиск по номеру")])
    keyboard.append([KeyboardButton("⬅️ Назад в админ-меню")])
    
    context.user_data['admin_users_page'] = page
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU

async def admin_navigate_pages(update: Update, context):
    """Обработчик навигации по страницам списка пользователей"""
    text = update.message.text
    current_page = context.user_data.get('admin_users_page', 0)
    
    if text == "⬅️ Предыдущая":
        context.user_data['admin_users_page'] = current_page - 1
    elif text == "➡️ Следующая":
        context.user_data['admin_users_page'] = current_page + 1
    
    return await admin_show_all_users_list(update, context)

async def admin_download_csv(update: Update, context):
    """Скачивание CSV файла"""
    try:
        csv_data = generate_users_csv()
        file = io.BytesIO(csv_data.encode('utf-8'))
        file.name = f"users_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        await update.message.reply_document(
            document=file,
            filename=file.name,
            caption="📊 Полные данные пользователей в CSV формате"
        )
        logger.info("Админ скачал CSV файл с данными пользователей")
        return await admin_menu_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка при генерации CSV файла: {e}")
        await update.message.reply_text("❌ Произошла ошибка при генерации файла.")
        return ADMIN_MENU

async def admin_exit(update: Update, context):
    """Выход из админ-панели"""
    await update.message.reply_text("👋 Выход из админ-панели.")
    await send_main_menu(update, context)
    context.user_data.pop('admin_selected_user', None)
    context.user_data.pop('admin_users_page', None)
    return ConversationHandler.END

# =====================================================================
# 8. КАЛОРИЙНОСТЬ
# =====================================================================

async def show_calorie_menu(update: Update, context):
    """Главное меню раздела калорийности"""
    keyboard = [
        [KeyboardButton("➕ Записать калории"), KeyboardButton("📅 История калорий")],
        [KeyboardButton("🎯 Установить цель"), KeyboardButton("🗑️ Удалить запись")],
        [KeyboardButton("📤 Экспорт данных"), KeyboardButton("⬅️ Назад в главное меню")]
    ]
    await update.message.reply_text(
        "📊 **Раздел 'Калорийность'**\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== ФУНКЦИЯ ДЛЯ ПОЗДРАВЛЕНИЯ С ДОСТИЖЕНИЕМ ЦЕЛИ =====
async def check_and_send_congrats(update: Update, user_id: int):
    """Проверяет, достиг ли пользователь цели, и отправляет поздравление"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(calories) FROM CalorieLog
        WHERE user_id = ? AND log_date = ?
    """, (user_id, today))
    total_today = cursor.fetchone()[0] or 0
    conn.close()
    
    goal = get_user_calorie_goal(user_id)
    
    if total_today <= goal and total_today > 0:
        await send_image_if_exists(
            update,
            "images/congrats.png",
            f"🎉 **Поздравляем!** 🎉\n\n"
            f"Вы уложились в норму калорий!\n"
            f"📊 Сегодня: {total_today} / {goal} ккал\n\n"
            f"Так держать! 💪"
        )
        return True
    return False

async def record_calorie_start(update: Update, context):
    """Начало записи калорий - показываем выбор приема пищи"""
    logger.info("record_calorie_start вызван")
    keyboard = [
        [KeyboardButton("🍳 Завтрак"), KeyboardButton("🍲 Обед")],
        [KeyboardButton("🍱 Ужин"), KeyboardButton("🍎 Перекус")],
        [KeyboardButton("⬅️ Назад в калории")]
    ]
    await update.message.reply_text(
        "🍽️ Выберите прием пищи:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CALORIE_MEAL_TYPE

async def record_calorie_meal_type(update: Update, context):
    text = update.message.text
    logger.info(f"record_calorie_meal_type: получен текст '{text}'")
    
    if text == "⬅️ Назад в калории":
        await update.message.reply_text("Запись калорий отменена.")
        await show_calorie_menu(update, context)
        context.user_data.pop('calorie_meal_type', None)
        return ConversationHandler.END
    
    meal_type_map = {
        "🍳 Завтрак": "breakfast", 
        "🍲 Обед": "lunch", 
        "🍱 Ужин": "dinner", 
        "🍎 Перекус": "snack"
    }
    
    if text in meal_type_map:
        context.user_data['calorie_meal_type'] = meal_type_map[text]
        
        # ===== ПОКАЗЫВАЕМ КАРТИНКУ В СООТВЕТСТВИИ С ПРИЁМОМ ПИЩИ =====
        meal_images = {
            "🍳 Завтрак": ("images/breakfast.png", "🍳 **Пример завтрака:** Овсяная каша с ягодами — 320 ккал"),
            "🍲 Обед": ("images/lunch.png", "🍲 **Пример обеда:** Греческий салат с курицей — 450 ккал"),
            "🍱 Ужин": ("images/dinner.png", "🍱 **Пример ужина:** Запечённый лосось с овощами — 520 ккал"),
            "🍎 Перекус": ("images/perekus.png", "🍎 **Пример перекуса:** Яблоко с орехами — 180 ккал")  # для перекуса нет отдельной картинки, только текст
        }
        
        img_path, caption = meal_images.get(text, (None, None))
        if img_path and img_path is not None:
            await send_image_if_exists(update, img_path, caption)
        elif caption:
            await update.message.reply_text(caption, parse_mode='Markdown')
        
        # ===== ПОКАЗЫВАЕМ ПРИМЕРЫ ВВОДА =====
        await update.message.reply_text(
            f"📝 Введите данные для **{text}**\n\n"
            "✅ **Примеры ввода:**\n"
            "• `350`\n"
            "• `350 Овсяная каша`\n"
            "• `350 30 10 45`\n"
            "• `350 30 10 45 Овсяная каша`\n\n"
            "Порядок БЖУ: **белки, жиры, углеводы**\n\n"
            "Введите данные:",
            parse_mode='Markdown'
        )
        return CALORIE_AMOUNT
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите прием пищи из меню:",
            reply_markup=ReplyKeyboardMarkup([
                ["🍳 Завтрак", "🍲 Обед"],
                ["🍱 Ужин", "🍎 Перекус"],
                ["⬅️ Назад в калории"]
            ], resize_keyboard=True)
        )
        return CALORIE_MEAL_TYPE

async def record_calorie_amount(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"record_calorie_amount: получен текст '{text}'")
    
    menu_buttons = [
        "⬅️ Назад в калории", "⬅️ Назад в главное меню",
        "🍳 Завтрак", "🍲 Обед", "🍱 Ужин", "🍎 Перекус",
        "➕ Записать калории", "📅 История калорий", 
        "🎯 Установить цель", "🗑️ Удалить запись", "📤 Экспорт данных",
        "🍽️ Питание", "👤 Профиль", "📊 Калорийность", "💳 Подписка"
    ]
    
    if text in menu_buttons:
        await update.message.reply_text("❌ Ввод отменён.")
        context.user_data.pop('calorie_meal_type', None)
        await show_calorie_menu(update, context)
        return ConversationHandler.END
    
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден в БД.")
        return ConversationHandler.END
    user_id = user_data[0]
    
    try:
        if text.isdigit():
            calories = int(text)
            protein = fat = carbs = 0
            food_description = None
        else:
            parts = text.split()
            if not parts[0].isdigit():
                raise ValueError("Первое значение должно быть числом")
            calories = int(parts[0])
            protein = fat = carbs = 0
            idx = 1
            if len(parts) >= 4:
                if (parts[1].replace('.', '').isdigit() and 
                    parts[2].replace('.', '').isdigit() and 
                    parts[3].replace('.', '').isdigit()):
                    protein = float(parts[1])
                    fat = float(parts[2])
                    carbs = float(parts[3])
                    idx = 4
            if idx < len(parts):
                food_description = ' '.join(parts[idx:])
            else:
                food_description = None
        
        if calories <= 0 or calories > 10000:
            await update.message.reply_text("❌ Количество калорий должно быть от 1 до 10000.")
            return CALORIE_AMOUNT
        
        meal_type = context.user_data.get('calorie_meal_type')
        if not meal_type:
            await update.message.reply_text("❌ Ошибка: не выбран прием пищи. Попробуйте снова.")
            await show_calorie_menu(update, context)
            return ConversationHandler.END
        
        log_date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO CalorieLog (user_id, log_date, meal_type, food_description, calories, protein, fat, carbs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, log_date, meal_type, food_description, calories, protein, fat, carbs))
        conn.commit()
        
        cursor.execute("""
            SELECT SUM(calories) FROM CalorieLog 
            WHERE user_id = ? AND log_date = ?
        """, (user_id, log_date))
        total_today = cursor.fetchone()[0] or 0
        conn.close()
        
        meal_type_ru = {"breakfast": "Завтрак", "lunch": "Обед", "dinner": "Ужин", "snack": "Перекус"}
        response = f"✅ Записано: {calories} ккал"
        if protein or fat or carbs:
            response += f" (Б:{protein:.0f} Ж:{fat:.0f} У:{carbs:.0f})"
        response += f" для {meal_type_ru.get(meal_type, meal_type)}"
        if food_description:
            response += f"\n📝 {food_description}"
        
        goal = get_user_calorie_goal(user_id)
        response += f"\n\n📊 Итого сегодня: {total_today} / {goal} ккал"
        
        await update.message.reply_text(response)
        
        # ===== ПРОВЕРЯЕМ И ОТПРАВЛЯЕМ ПОЗДРАВЛЕНИЕ =====
        await check_and_send_congrats(update, user_id)
        
        context.user_data.pop('calorie_meal_type', None)
        await show_calorie_menu(update, context)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат.\n\n"
            "✅ **Правильные примеры:**\n"
            "• `350` — только калории\n"
            "• `350 Овсяная каша` — калории и описание\n"
            "• `350 30 10 45` — калории, белки, жиры, углеводы\n"
            "• `350 30 10 45 Овсяная каша` — полный формат\n\n"
            "Порядок БЖУ: **белки, жиры, углеводы**",
            parse_mode='Markdown'
        )
        return CALORIE_AMOUNT
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        await update.message.reply_text("❌ Произошла ошибка при сохранении. Попробуйте ещё раз.")
        return CALORIE_AMOUNT

async def show_calorie_history_menu(update: Update, context):
    """Показывает меню выбора периода истории калорий"""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    subscription_status = 'free'
    
    if user_data:
        user_id = user_data[0]
        subscription_status = get_user_subscription_status(user_id)
    
    has_paid_subscription = subscription_status in ['week_200', 'month_350', 'trial']
    
    keyboard = [
        [KeyboardButton("📅 Сегодня")]
    ]
    
    if has_paid_subscription:
        keyboard.append([KeyboardButton("📅 За последние 7 дней"), KeyboardButton("📅 За последние 30 дней")])
    else:
        keyboard.append([KeyboardButton("🔒 За последние 7 дней (нужна подписка"), KeyboardButton("🔒 За последние 30 дней (нужна подписка")])
    
    keyboard.append([KeyboardButton("⬅️ Назад в калории")])
    
    message_text = "📅 **История калорий**\n\n"
    if not has_paid_subscription:
        message_text += "🔓 **Бесплатно доступно:** просмотр за сегодня\n"
        message_text += "⭐ **С подпиской:** просмотр за 7 и 30 дней\n\n"
    
    message_text += "Выберите период:"
    
    await update.message.reply_text(
        message_text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def show_calorie_history(update: Update, context, start_date: str, end_date: str, period_name: str):
    """Показывает историю калорий за период"""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return
    user_id = user_data[0]
    
    days = 1
    if period_name != "сегодня":
        try:
            days = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days + 1
        except:
            days = 7 if "7" in period_name else 30
    
    if days > 1:
        subscription_status = get_user_subscription_status(user_id)
        if subscription_status not in ['week_200', 'month_350', 'trial']:
            await update.message.reply_text(
                "🔒 **Доступ к истории за этот период требует подписки!**\n\n"
                f"📊 Период: {period_name}\n\n"
                "Оформите подписку в разделе '💳 Подписка', чтобы получить доступ к расширенной статистике.\n\n"
                "🔓 **Бесплатно доступно:** просмотр за сегодня",
                parse_mode='Markdown'
            )
            return
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT log_date, SUM(calories), SUM(protein), SUM(fat), SUM(carbs)
        FROM CalorieLog
        WHERE user_id = ? AND log_date BETWEEN ? AND ?
        GROUP BY log_date
        ORDER BY log_date DESC
    """, (user_id, start_date, end_date))
    history = cursor.fetchall()
    conn.close()
    
    if not history:
        await update.message.reply_text(f"📊 За {period_name} нет данных о калориях.\n\nДобавьте записи через '➕ Записать калории'")
        return
    
    response = f"📊 **История калорий за {period_name}**\n\n"
    total_calories = 0
    goal = get_user_calorie_goal(user_id)
    goal_days = 0
    
    history_to_show = history[:14] if len(history) > 14 else history
    
    for date_str, calories, protein, fat, carbs in history_to_show:
        try:
            date_formatted = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m')
        except:
            date_formatted = date_str
        goal_status = "✅" if calories <= goal else "⚠️"
        if calories <= goal:
            goal_days += 1
        response += f"**{date_formatted}:** {calories} ккал {goal_status}\n"
        total_calories += calories
    
    if len(history) > 14:
        response += f"\n... и еще {len(history) - 14} дней\n"
    
    avg_calories = total_calories / len(history_to_show) if len(history_to_show) > 0 else 0
    goal_percentage = (goal_days / len(history_to_show)) * 100 if len(history_to_show) > 0 else 0
    
    response += f"\n**📈 Статистика:**\n"
    response += f"• Среднее: {avg_calories:.0f} ккал/день\n"
    response += f"• Выполнение цели: {goal_days}/{len(history_to_show)} ({goal_percentage:.0f}%)\n"
    response += f"• Всего: {total_calories} ккал"
    
    keyboard = [[KeyboardButton("⬅️ Назад в историю")]]
    await update.message.reply_text(response, parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def handle_calorie_history_buttons(update: Update, context):
    """Обработчик кнопок истории калорий (вызывается из handle_message)"""
    text = update.message.text
    logger.info(f"=== ОБРАБОТКА ИСТОРИИ КАЛОРИЙ: {text} ===")
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    if text == "📅 Сегодня":
        logger.info("Показываем историю за сегодня")
        await show_calorie_history(update, context, today, today, "сегодня")
        return True
    
    elif text == "📅 За последние 7 дней":
        logger.info("Проверка подписки для 7 дней")
        telegram_id = update.effective_user.id
        user_data = get_user_data_by_telegram_id(telegram_id)
        if user_data:
            user_id = user_data[0]
            subscription_status = get_user_subscription_status(user_id)
            if subscription_status in ['week_200', 'month_350', 'trial']:
                start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                await show_calorie_history(update, context, start, today, "последние 7 дней")
            else:
                await show_subscription_required_message(update)
        return True
    
    elif text == "📅 За последние 30 дней":
        logger.info("Проверка подписки для 30 дней")
        telegram_id = update.effective_user.id
        user_data = get_user_data_by_telegram_id(telegram_id)
        if user_data:
            user_id = user_data[0]
            subscription_status = get_user_subscription_status(user_id)
            if subscription_status in ['week_200', 'month_350', 'trial']:
                start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                await show_calorie_history(update, context, start, today, "последние 30 дней")
            else:
                await show_subscription_required_message(update)
        return True
    
    elif text in ["🔒 За последние 7 дней (нужна подписка", "🔒 7 дней (нужна подписка"]:
        logger.info("Нажата заблокированная кнопка 7 дней")
        await show_subscription_required_message(update)
        return True
    
    elif text in ["🔒 За последние 30 дней (нужна подписка", "🔒 30 дней (нужна подписка"]:
        logger.info("Нажата заблокированная кнопка 30 дней")
        await show_subscription_required_message(update)
        return True
    
    return False

async def show_subscription_required_message(update: Update):
    """Показывает сообщение о необходимости подписки с кнопкой перехода"""
    keyboard = [
        [KeyboardButton("💳 Перейти в раздел подписки")],
        [KeyboardButton("⬅️ Назад в историю")]
    ]
    await update.message.reply_text(
        "🔒 **Доступ к истории за этот период требует подписки!**\n\n"
        "📊 С подпиской вам доступно:\n"
        "• История калорий за 7 и 30 дней\n"
        "• Персональный рацион на неделю\n"
        "• Расширенная статистика\n\n"
        "💰 **Тарифы:**\n"
        "• Недельная подписка — 200₽\n"
        "• Месячная подписка — 350₽\n"
        "• Пробный день — бесплатно 🎁\n\n"
        "Нажмите на кнопку ниже, чтобы оформить подписку:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def set_calorie_goal_start(update: Update, context):
    await update.message.reply_text("Введите вашу дневную цель по калориям (например, 2000):")
    return CALORIE_GOAL_SETTING

async def set_calorie_goal_handler(update: Update, context):
    text = update.message.text.strip()
    logger.info(f"set_calorie_goal_handler: получен текст '{text}'")
    
    menu_buttons = [
        "⬅️ Назад в калории", "⬅️ Назад в главное меню",
        "🍽️ Питание", "👤 Профиль", "📊 Калорийность", "💳 Подписка",
        "➕ Записать калории", "📅 История калорий", "🎯 Установить цель",
        "🗑️ Удалить запись", "📤 Экспорт данных"
    ]
    
    if text in menu_buttons:
        await update.message.reply_text("❌ Установка цели отменена.")
        await show_calorie_menu(update, context)
        return ConversationHandler.END
    
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден в БД.")
        return ConversationHandler.END
    user_id = user_data[0]
    
    try:
        calorie_goal = int(text)
        if calorie_goal < 500 or calorie_goal > 10000:
            await update.message.reply_text("❌ Пожалуйста, введите корректное значение (500-10000 ккал):")
            return CALORIE_GOAL_SETTING
        
        update_calorie_goal(user_id, calorie_goal=calorie_goal)
        await update.message.reply_text(f"✅ Цель по калориям установлена: **{calorie_goal} ккал/день**", parse_mode='Markdown')
        await show_calorie_menu(update, context)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число (например: 2000):")
        return CALORIE_GOAL_SETTING

async def export_calorie_data(update: Update, context):
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден в БД.")
        return
    user_id = user_data[0]
    try:
        csv_data = generate_user_calorie_csv(user_id)
        file = io.BytesIO(csv_data.encode('utf-8'))
        file.name = f"calorie_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        await update.message.reply_document(
            document=file,
            filename=file.name,
            caption="📊 Ваши данные о калориях в CSV формате"
        )
        logger.info(f"Пользователь {telegram_id} скачал свои данные о калориях")
    except Exception as e:
        logger.error(f"Ошибка при генерации CSV файла: {e}")
        await update.message.reply_text("❌ Произошла ошибка при генерации файла.")

async def delete_calorie_record_start(update: Update, context):
    """Начало удаления записей калорий"""
    telegram_id = update.effective_user.id
    user_data = get_user_data_by_telegram_id(telegram_id)
    if not user_data:
        await update.message.reply_text("Ошибка: Пользователь не найден.")
        return
    
    user_id = user_data[0]
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_log, log_date, meal_type, calories, food_description
        FROM CalorieLog
        WHERE user_id = ?
        ORDER BY log_date DESC, id_log DESC
        LIMIT 10
    """, (user_id,))
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        await update.message.reply_text("📭 У вас пока нет записей калорий для удаления.")
        await show_calorie_menu(update, context)
        return ConversationHandler.END
    
    text = "🗑️ **Удаление записей калорий**\n\n"
    text += "Введите номер записи, которую хотите удалить:\n\n"
    
    meal_type_ru = {"breakfast": "🍳 Завтрак", "lunch": "🍲 Обед", "dinner": "🍱 Ужин", "snack": "🍎 Перекус"}
    
    for i, (record_id, log_date, meal_type, calories, description) in enumerate(records, 1):
        try:
            date_formatted = datetime.strptime(log_date, '%Y-%m-%d').strftime('%d.%m')
        except:
            date_formatted = log_date
        meal_ru = meal_type_ru.get(meal_type, meal_type)
        text += f"{i}. {date_formatted} {meal_ru}: {calories} ккал"
        if description:
            text += f" - {description[:30]}"
        text += f" (ID: {record_id})\n"
    
    text += "\nВведите **номер** записи (1-10) или нажмите ❌ Отмена"
    
    context.user_data['delete_records_list'] = records
    context.user_data['awaiting_delete_selection'] = True
    
    keyboard = [[KeyboardButton("❌ Отмена")]]
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return DELETE_CALORIE_RECORD

async def process_delete_calorie_record(update: Update, context):
    """Обработка удаления записи калорий"""
    text = update.message.text
    
    if text == "❌ Отмена" or text == "⬅️ Назад в калории":
        await show_calorie_menu(update, context)
        context.user_data.pop('delete_records_list', None)
        context.user_data.pop('awaiting_delete_selection', None)
        return ConversationHandler.END
    
    records = context.user_data.get('delete_records_list')
    if not records:
        await update.message.reply_text("Ошибка: список записей не найден.")
        await show_calorie_menu(update, context)
        return ConversationHandler.END
    
    try:
        selection = int(text)
        if 1 <= selection <= len(records):
            record_id = records[selection - 1][0]
            
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM CalorieLog WHERE id_log = ?", (record_id,))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f"✅ Запись #{selection} успешно удалена!")
            await show_calorie_menu(update, context)
        else:
            await update.message.reply_text(f"❌ Пожалуйста, введите число от 1 до {len(records)}")
            return DELETE_CALORIE_RECORD
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите номер записи (число)")
        return DELETE_CALORIE_RECORD
    
    context.user_data.pop('delete_records_list', None)
    context.user_data.pop('awaiting_delete_selection', None)
    return ConversationHandler.END

# =====================================================================
# 9. ОБЩИЙ ОБРАБОТЧИК СООБЩЕНИЙ
# =====================================================================

async def handle_message(update: Update, context):
    text = update.message.text
    logger.info(f"Обработка сообщения: {text}")
    
    if text in ["🔒 За последние 7 дней (нужна подписка", "🔒 За последние 30 дней (нужна подписка"]:
        keyboard = [
            [KeyboardButton("💳 Перейти в раздел подписки")],
            [KeyboardButton("⬅️ Назад в историю")]
        ]
        await update.message.reply_text(
            "🔒 **Доступ к истории за этот период требует подписки!**\n\n"
            "💰 **Тарифы:**\n"
            "• Недельная подписка — 200₽\n"
            "• Месячная подписка — 350₽\n"
            "• Пробный день — бесплатно 🎁\n\n"
            "Нажмите на кнопку ниже, чтобы оформить подписку:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    
    if text in ["📝 Изменить возраст", "📝 Изменить рост", "📝 Изменить вес", "📋 История изменений", "✏️ Изменить данные", "📝 Изменить еще данные"]:
        await edit_profile_start(update, context)
        return
    
    if text == "💳 Перейти в раздел подписки":
        await show_subscription_menu(update, context)
        return
    
    if text in ["📅 Сегодня", "📅 За последние 7 дней", "📅 За последние 30 дней"]:
        await handle_calorie_history_buttons(update, context)
        return

    if text == "📅 Составить рацион":
        return await show_ration_options(update, context)
    elif text == "📅 Составить еще рацион":
        return await show_ration_options(update, context)

    if text == "🍽️ Питание":
        await show_nutrition_menu(update, context)
    elif text == "👤 Профиль":
        await show_profile(update, context)
    elif text == "📊 Калорийность":
        await show_calorie_menu(update, context)
    elif text == "💳 Подписка":
        await show_subscription_menu(update, context)
    elif text == "📅 История калорий":
        await show_calorie_history_menu(update, context)
    elif text == "⬅️ Назад в историю":
        await show_calorie_history_menu(update, context)
    elif text == "⬅️ Назад в калории":
        await show_calorie_menu(update, context)
    elif text == "ℹ️ Моя подписка":
        await show_my_subscription(update, context)
    elif text == "📊 Детальная статистика":
        await show_detailed_stats(update, context)
    elif text == "🎯 Мои цели":
        await show_goals_menu(update, context)
    elif text == "📈 График веса":
        await show_weight_chart_info(update, context)
    elif text == "📋 История веса":
        await show_weight_history(update, context)
    elif text == "⬅️ Назад в главное меню":
        await send_main_menu(update, context)
    elif text == "⬅️ Назад в профиль":
        await show_profile(update, context)
    elif text == "⬅️ Назад в питание":
        await show_nutrition_menu(update, context)
    elif text == "⬅️ Назад к статистике веса":
        await show_weight_chart_info(update, context)
    elif text == "➕ Записать калории":
        return await record_calorie_start(update, context)
    elif text == "🎯 Установить цель":
        return await set_calorie_goal_start(update, context)
    elif text == "🗑️ Удалить запись":
        return await delete_calorie_record_start(update, context)
    elif text == "📤 Экспорт данных":
        await export_calorie_data(update, context)
    elif text == "📝 Обновить вес":
        await update_weight_start(update, context)
    else:
        try:
            float(text)
            return
        except ValueError:
            logger.debug(f"Игнорируем сообщение: {text}")

# =====================================================================
# 10. ЗАПУСК БОТА
# =====================================================================

def main():
    init_db()
    debug_database()
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрация
    registration_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GETTING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GETTING_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            GETTING_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(registration_conv_handler)
    
    # Редактирование профиля
    edit_profile_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ Изменить данные$"), edit_profile_start),
            MessageHandler(filters.Regex("^📝 Изменить еще данные$"), edit_profile_start),
            MessageHandler(filters.Regex("^📝 Обновить вес$"), update_weight_start),
        ],
        states={
            EDITING_PROFILE_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_profile_choice)],
            EDIT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_age_handler)],
            EDIT_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_height_handler)],
            EDIT_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_weight_handler)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^⬅️ Назад в профиль$"), show_profile),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    application.add_handler(edit_profile_conv_handler)
    
    # Питание (рацион)
    nutrition_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📅 Составить рацион$"), show_ration_options),
            MessageHandler(filters.Regex("^📅 Составить еще рацион$"), show_ration_options),
        ],
        states={
            RATION_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_ration_goal)],
            RATION_GOAL: [MessageHandler(filters.Regex(r"^(💪 Набор массы|⚖️ Поддержание веса|📉 Диета \(похудение\))$"), get_ration_from_giga)],
            NAVIGATE_RATION: [
                MessageHandler(filters.Regex("^◀️ Назад$"), navigate_ration),
                MessageHandler(filters.Regex("^Вперед ▶️$"), navigate_ration),
                MessageHandler(filters.Regex("^📋 Показать всё текстом$"), navigate_ration),
                MessageHandler(filters.Regex("^📅 Новый рацион$"), navigate_ration),
                MessageHandler(filters.Regex("^⬅️ Назад в питание$"), navigate_ration),
                MessageHandler(filters.Regex("^⬅️ Назад в главное меню$"), navigate_ration),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^⬅️ Назад в питание$"), show_nutrition_menu),
            MessageHandler(filters.Regex("^⬅️ Назад в главное меню$"), send_main_menu),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    application.add_handler(nutrition_conv_handler)

    # Подписка
    subscription_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 Подписка$"), show_subscription_menu)],
        states={
            SUBSCRIPTION_MENU_CHOICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_subscription_choice
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(subscription_conv_handler)
    
    # Калорийность
    calorie_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📊 Калорийность$"), show_calorie_menu),
            MessageHandler(filters.Regex("^➕ Записать калории$"), record_calorie_start),
            MessageHandler(filters.Regex("^🎯 Установить цель$"), set_calorie_goal_start),
            MessageHandler(filters.Regex("^🗑️ Удалить запись$"), delete_calorie_record_start),
            MessageHandler(filters.Regex("^📤 Экспорт данных$"), export_calorie_data),
        ],
        states={
            CALORIE_MEAL_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_calorie_meal_type)],
            CALORIE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_calorie_amount)],
            CALORIE_GOAL_SETTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_calorie_goal_handler)],
            DELETE_CALORIE_RECORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_delete_calorie_record)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^⬅️ Назад в калории$"), show_calorie_menu),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    application.add_handler(calorie_conv_handler)

    # Админ-панель
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_command)],
        states={
            ADMIN_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_login_handler)],
            ADMIN_PASSWORD_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_password_handler)],
            ADMIN_MENU: [
                MessageHandler(filters.Regex("^🔍 Поиск пользователя по номеру$"), admin_search_by_number_start),
                MessageHandler(filters.Regex("^📋 Список всех пользователей$"), admin_show_all_users_list),
                MessageHandler(filters.Regex("^📥 Скачать CSV файл$"), admin_download_csv),
                MessageHandler(filters.Regex("^⬅️ Выйти из админ-панели$"), admin_exit),
                MessageHandler(filters.Regex("^⬅️ Предыдущая$"), admin_navigate_pages),
                MessageHandler(filters.Regex("^➡️ Следующая$"), admin_navigate_pages),
                MessageHandler(filters.Regex("^⬅️ Назад в админ-меню$"), admin_menu_handler),
            ],
            ADMIN_SEARCH_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_show_user_by_number),
                MessageHandler(filters.Regex("^⬅️ Назад в админ-меню$"), admin_menu_handler),
            ],
            ADMIN_USER_CONTROL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handle_subscription_action),
                MessageHandler(filters.Regex("^⬅️ Назад в админ-меню$"), admin_menu_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(admin_conv_handler)
    
    # Обычные обработчики
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Regex("^🍽️ Питание$"), show_nutrition_menu))
    application.add_handler(MessageHandler(filters.Regex("^👤 Профиль$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^📊 Детальная статистика$"), show_detailed_stats))
    application.add_handler(MessageHandler(filters.Regex("^🎯 Мои цели$"), show_goals_menu))
    application.add_handler(MessageHandler(filters.Regex("^📈 График веса$"), show_weight_chart_info))
    application.add_handler(MessageHandler(filters.Regex("^📤 Экспорт данных$"), export_calorie_data))
    application.add_handler(MessageHandler(filters.Regex("^📋 История веса$"), show_weight_history))
    application.add_handler(MessageHandler(filters.Regex("^📋 История изменений$"), show_profile_history))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад в главное меню$"), send_main_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад в профиль$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад в калории$"), show_calorie_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад в историю$"), show_calorie_history_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад в питание$"), show_nutrition_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад к статистике веса$"), show_weight_chart_info))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад к целям$"), show_goals_menu))
    application.add_handler(MessageHandler(filters.Regex("^🎯 Установить цель$"), set_calorie_goal_start))
    application.add_handler(MessageHandler(filters.Regex("^ℹ️ Моя подписка$"), show_my_subscription))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен.")
    application.run_polling()

if __name__ == '__main__':
    main()