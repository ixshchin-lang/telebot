from config import *
import pandas as pd


async def menu_admin(update, context):
    """Показывает меню админа"""
    await update.message.reply_text("👑 Админ-панель", reply_markup=admin_kb())


async def kol_family(update, context):
    """Показывает статистику по семьям"""
    try:
        # Инициализация файлов
        init_data_files()

        message = "📊 СТАТИСТИКА СИСТЕМЫ\n\n"

        # Статистика семей
        if os.path.exists(FAMILY_FILE):
            df_families = pd.read_csv(FAMILY_FILE)
            families_count = len(df_families)
            message += f"👥 Семей создано: {families_count}\n"
        else:
            message += "👥 Семей создано: 0\n"

        # Статистика настроения
        if os.path.exists(WOMEN_FILE):
            df_mood = pd.read_csv(WOMEN_FILE)
            mood_count = len(df_mood)
            message += f"📝 Записей настроения: {mood_count}\n"
        else:
            message += "📝 Записей настроения: 0\n"

        # Статистика желаний
        if os.path.exists(WISH_FILE):
            df_wishes = pd.read_csv(WISH_FILE)
            wishes_count = len(df_wishes)
            done_wishes = len(df_wishes[df_wishes['is_done'] == True])
            message += f"💭 Желаний добавлено: {wishes_count}\n"
            message += f"✅ Выполнено желаний: {done_wishes}\n"
        else:
            message += "💭 Желаний добавлено: 0\n"
            message += "✅ Выполнено желаний: 0\n"

        # Последние семьи
        if 'df_families' in locals() and families_count > 0:
            message += f"\n📈 Последние семьи:\n"
            last_families = df_families.tail(3).iloc[::-1]
            for i, (_, family) in enumerate(last_families.iterrows(), 1):
                message += f"{i}. 👰 {family['women']} + 🤵 {family['men']}\n"
                message += f"   🔑 {family['key']}\n"

        await update.message.reply_text(message, reply_markup=admin_kb())

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=admin_kb())


async def show_admin_panel(update, context):
    """Показывает админ-панель при вводе пароля"""
    text = update.message.text.strip()

    if text == ADMIN_PASSWORD:
        await update.message.reply_text(
            "✅ Пароль верный! Добро пожаловать в админ-панель!",
            reply_markup=admin_kb()
        )
        context.user_data['is_admin'] = True
        return True

    return False