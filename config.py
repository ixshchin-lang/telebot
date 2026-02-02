from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import hashlib
import pandas as pd
import os

# КОНФИГУРАЦИЯ
TOKEN = "8405905845:AAHZTOQkTF1E82b8TGBgKNkE-GNInd6E684"
ADMIN_PASSWORD = "2002"
FAMILY_FILE = "data/key_family.csv"
WOMEN_FILE = "data/status_women.csv"
WISH_FILE = "data/wishes.csv"

# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
family_dialogs = {}
wish_pagination = {}


# =========== КЛАВИАТУРЫ ===========

def admin_kb():
    """Клавиатура админ-панели"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("👥 Статистика семей"), KeyboardButton("📊 Общая статистика")],
        [KeyboardButton("⬅️ Назад в меню")]
    ], resize_keyboard=True)


def start_kb():
    """Клавиатура стартового меню"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🤝 Создать семью"), KeyboardButton("🔑 Войти по ключу")]
    ], resize_keyboard=True)


def main_kb():
    """Главное меню (выбор роли)"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🤵 Муж"), KeyboardButton("👰 Жена")]
    ], resize_keyboard=True)


def numbers_kb():
    """Клавиатура с цифрами 1-10"""
    buttons = [
        [KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3")],
        [KeyboardButton("4"), KeyboardButton("5"), KeyboardButton("6")],
        [KeyboardButton("7"), KeyboardButton("8"), KeyboardButton("9")],
        [KeyboardButton("10"), KeyboardButton("🚫 Отмена")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)


def husband_main_kb():
    """Основное меню для мужа"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("😊 Состояние жены"), KeyboardButton("💭 Желания жены")],
        [KeyboardButton("⭐ Мои желания"), KeyboardButton("➕ Добавить желание")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)


def wife_main_kb():
    """Основное меню для жены"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📝 Моё настроение"), KeyboardButton("⭐ Мои желания")],
        [KeyboardButton("💭 Желания мужа"), KeyboardButton("➕ Добавить желание")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)


def wish_type_kb():
    """Выбор типа желания"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("✨ Моральное"), KeyboardButton("🛍️ Покупка")],
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)


def back_only_kb():
    """Клавиатура только с кнопкой Назад"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("⬅️ Назад")]
    ], resize_keyboard=True)


def wish_control_kb(wish_id, is_my_wish=True, current_page=0, total_pages=1):
    """Инлайн-клавиатура для управления желанием"""
    buttons = []

    if is_my_wish:
        buttons.append([
            InlineKeyboardButton("✅ Выполнено", callback_data=f"done_{wish_id}"),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{wish_id}")
        ])

    # Кнопки навигации
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{wish_id}"))

    nav_buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="page_info"))

    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"next_{wish_id}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)


# =========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===========

def init_data_files():
    """Инициализирует все необходимые файлы данных"""
    os.makedirs('data', exist_ok=True)

    # Файл семей
    if not os.path.exists(FAMILY_FILE):
        pd.DataFrame(columns=['women', 'men', 'key', 'created_at']).to_csv(FAMILY_FILE, index=False)

    # Файл настроения
    if not os.path.exists(WOMEN_FILE):
        pd.DataFrame(columns=['family_key', 'user_id', 'mood', 'health', 'date', 'time']).to_csv(WOMEN_FILE,
                                                                                                 index=False)

    # Файл желаний
    if not os.path.exists(WISH_FILE):
        columns = ['id', 'family_key', 'user_id', 'user_role', 'type', 'title',
                   'price', 'expected_mood', 'created_at', 'is_done']
        pd.DataFrame(columns=columns).to_csv(WISH_FILE, index=False)

    print("✅ Все файлы данных инициализированы")


def generate_key(wife, husband):
    """Генерирует уникальный ключ для семьи"""
    text = f"{wife}{husband}{datetime.now().timestamp()}"
    return hashlib.md5(text.encode()).hexdigest()[:8].upper()


def get_family_info(key):
    """Возвращает информацию о семье по ключу"""
    try:
        if not os.path.exists(FAMILY_FILE):
            return None

        df = pd.read_csv(FAMILY_FILE)
        family_data = df[df['key'] == str(key).strip()]

        if not family_data.empty:
            family = family_data.iloc[0]
            return {
                'wife_name': family['women'],
                'husband_name': family['men'],
                'key': family['key']
            }
    except Exception as e:
        print(f"❌ Ошибка при получении информации о семье: {e}")
    return None


def check_family_key(key):
    """Проверяет существование ключа семьи"""
    try:
        if not os.path.exists(FAMILY_FILE):
            return False

        df = pd.read_csv(FAMILY_FILE)
        return str(key).strip() in df['key'].astype(str).str.strip().values
    except Exception as e:
        print(f"❌ Ошибка при проверке ключа: {e}")
        return False


def get_wish_by_id(wish_id):
    """Находит желание по ID"""
    try:
        if not os.path.exists(WISH_FILE):
            return None

        df = pd.read_csv(WISH_FILE)
        df['id'] = df['id'].astype(str)
        wish_data = df[df['id'] == str(wish_id)]

        if not wish_data.empty:
            return wish_data.iloc[0].to_dict()
    except Exception as e:
        print(f"❌ Ошибка при получении желания: {e}")
    return None