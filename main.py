from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import *
from admin import menu_admin, kol_family, show_admin_panel
from family_manager import create_family
from mood_tracker import (husband_menu, wife_menu, start_mood_recording,
                          show_wife_mood, handle_mood_rating)
from wish_manager import (start_add_wish, handle_wish_type, save_wish,
                          show_my_wishes, show_spouse_wishes, handle_wish_action)

print("🤖 Семейный бот запущен и готов служить!")


def has_family_access(context):
    """Проверяет, есть ли у пользователя доступ к семье"""
    return 'family_key' in context.user_data


async def start_command(update: Update, context):
    """Обрабатывает команду /start"""
    user = update.effective_user
    context.user_data.clear()

    message = f"👋 Привет, {user.first_name}!\n\n"
    message += "Добро пожаловать в Семейный Трекер!\n\n"
    message += "📋 Возможности:\n"
    message += "• 🤝 Создать семью\n"
    message += "• 📝 Отслеживать настроение\n"
    message += "• 💭 Записывать желания\n"
    message += "• ❤️ Укреплять отношения\n\n"
    message += "Выбери действие:"

    await update.message.reply_text(message, reply_markup=start_kb())


async def handle_key_entry(update: Update, context):
    """Обрабатывает ввод ключа семьи"""
    text = update.message.text.strip()

    if text == "🔑 Войти по ключу":
        context.user_data['waiting_key'] = True
        await update.message.reply_text("🔑 Введи семейный ключ:")
        return

    if context.user_data.get('waiting_key'):
        context.user_data['waiting_key'] = False

        if check_family_key(text):
            family_info = get_family_info(text)
            if family_info:
                context.user_data.update({
                    'family_key': text,
                    'wife_name': family_info['wife_name'],
                    'husband_name': family_info['husband_name']
                })
                message = f"🎉 Доступ открыт!\n\n"
                message += f"Приветствуем:\n"
                message += f"👰 {family_info['wife_name']}\n"
                message += f"🤵 {family_info['husband_name']}\n\n"
                message += f"Выбери свою роль:"
                await update.message.reply_text(message, reply_markup=main_kb())
            else:
                await update.message.reply_text("❌ Ошибка загрузки данных", reply_markup=start_kb())
        else:
            await update.message.reply_text("❌ Неверный ключ!", reply_markup=start_kb())


async def cancel_operation(update: Update, context):
    """Отменяет текущую операцию"""
    # Очистка временных данных
    for key in ['mood', 'health', 'waiting_for', 'waiting_key',
                'wish_type', 'wish_title', 'wish_price', 'wish_step']:
        context.user_data.pop(key, None)

    if has_family_access(context):
        user_role = context.user_data.get('user_role', '')
        if user_role == 'husband':
            await husband_menu(update, context)
        else:
            await wife_menu(update, context)
    else:
        await update.message.reply_text("Операция отменена", reply_markup=start_kb())


async def handle_message(update: Update, context):
    """Главный обработчик сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    print(f"📱 {user_id}: {text}")

    # ПРОВЕРКА АДМИН-ПАРОЛЯ
    if text == ADMIN_PASSWORD or context.user_data.get('is_admin'):
        if await show_admin_panel(update, context):
            return

    # ПРОВЕРКА АДМИН-КОМАНД
    if context.user_data.get('is_admin'):
        if text == "👥 Статистика семей":
            await kol_family(update, context)
            return
        elif text == "📊 Общая статистика":
            await kol_family(update, context)
            return
        elif text == "⬅️ Назад в меню":
            context.user_data.pop('is_admin', None)
            await start_command(update, context)
            return

    # СОЗДАНИЕ СЕМЬИ
    if user_id in family_dialogs or text == "🤝 Создать семью":
        if await create_family(update, context):
            return

    # ВВОД КЛЮЧА
    if context.user_data.get('waiting_key') or text == "🔑 Войти по ключу":
        await handle_key_entry(update, context)
        return

    # ОБРАБОТКА ВВОДА ЖЕЛАНИЙ
    if context.user_data.get('wish_step') in ['title', 'price', 'mood']:
        await save_wish(update, context)
        return

    # ПРОВЕРКА ДОСТУПА
    if not has_family_access(context):
        await update.message.reply_text("❌ Сначала войди в семью!", reply_markup=start_kb())
        return

    # ЦИФРЫ 1-10 (ОЦЕНКИ НАСТРОЕНИЯ)
    if text in [str(i) for i in range(1, 11)]:
        await handle_mood_rating(update, context)
        return

    # ОБРАБОТКА КОМАНД
    handlers = {
        # Основные команды
        "🤵 Муж": husband_menu,
        "👰 Жена": wife_menu,
        "⬅️ Назад": lambda u, c: u.message.reply_text("Главное меню:", reply_markup=main_kb()),

        # Для мужа
        "😊 Состояние жены": show_wife_mood,
        "💭 Желания жены": lambda u, c: show_spouse_wishes(u, c, 0),
        "⭐ Мои желания": lambda u, c: show_my_wishes(u, c, 0),
        "➕ Добавить желание": start_add_wish,

        # Для жены
        "📝 Моё настроение": start_mood_recording,
        "⭐ Мои желания": lambda u, c: show_my_wishes(u, c, 0),
        "💭 Желания мужа": lambda u, c: show_spouse_wishes(u, c, 0),
        "➕ Добавить желание": start_add_wish,

        # Общие
        "🚫 Отмена": cancel_operation,
        "✨ Моральное": handle_wish_type,
        "🛍️ Покупка": handle_wish_type,
    }

    if text in handlers:
        await handlers[text](update, context)
        return

    # НЕИЗВЕСТНАЯ КОМАНДА
    if has_family_access(context):
        await update.message.reply_text("🤔 Не понимаю команду...", reply_markup=main_kb())
    else:
        await update.message.reply_text("🤔 Не понимаю команду...", reply_markup=start_kb())


def main():
    """Главная функция запуска бота"""
    # Инициализация файлов
    init_data_files()

    # Создание приложения
    app = Application.builder().token(TOKEN).build()

    # ОБРАБОТЧИКИ
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_wish_action))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🎯 Бот готов к работе!")
    print(f"🔐 Пароль админки: {ADMIN_PASSWORD}")
    print("📱 Ожидаю сообщений...")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()