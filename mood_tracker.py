from config import *
import pandas as pd


async def husband_menu(update, context):
    """Основное меню для мужа"""
    context.user_data['user_role'] = 'husband'
    await update.message.reply_text(
        "🤵 Привет, командир!\n\nЧто делаем сегодня?",
        reply_markup=husband_main_kb()
    )


async def wife_menu(update, context):
    """Основное меню для жены"""
    context.user_data['user_role'] = 'wife'
    await update.message.reply_text(
        "👰 Здравствуй, моя хорошая!\n\nКак самочувствие сегодня?",
        reply_markup=wife_main_kb()
    )


async def start_mood_recording(update, context):
    """Начинает запись настроения жены"""
    context.user_data.update({'waiting_for': 'mood'})
    await update.message.reply_text(
        "😊 Расскажи, моя хорошая, как твое настроение от 1 до 10?\n\n"
        "1 - Плохо\n10 - Отлично!",
        reply_markup=numbers_kb()
    )


def save_mood_record(user_id, family_key, mood, health):
    """Сохраняет запись настроения в файл"""
    try:
        record = {
            'family_key': family_key,
            'user_id': user_id,
            'mood': mood,
            'health': health,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S')
        }

        # Чтение и добавление записи
        if os.path.exists(WOMEN_FILE) and os.path.getsize(WOMEN_FILE) > 0:
            df = pd.read_csv(WOMEN_FILE)
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        else:
            df = pd.DataFrame([record])

        df.to_csv(WOMEN_FILE, index=False)
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении настроения: {e}")
        return False


async def show_wife_mood(update, context):
    """Показывает последнее состояние жены"""
    family_key = context.user_data.get('family_key')
    wife_name = context.user_data.get('wife_name', 'любимой')

    if not family_key:
        await update.message.reply_text("❌ Нет доступа к данным семьи")
        return

    # Получение данных о настроении
    mood_data = get_last_wife_status(family_key)

    if mood_data['mood'] == "Нет данных":
        await update.message.reply_text(
            f"📊 Данных о {wife_name} пока нет.\n\nПопроси ее обновить настроение!",
            reply_markup=husband_main_kb()
        )
        return

    # Формирование сообщения
    mood_int = int(mood_data['mood'])
    health_int = int(mood_data['health'])

    # Эмодзи для настроения
    if mood_int <= 3:
        mood_emoji = "😢"
        advice = "⚠️ Внимание! Требуются срочные меры!"
    elif mood_int <= 6:
        mood_emoji = "😐"
        advice = "💡 Рекомендация: сделай комплимент!"
    elif mood_int <= 8:
        mood_emoji = "😊"
        advice = "🎉 Отлично! Продолжай в том же духе!"
    else:
        mood_emoji = "😍"
        advice = "🔥 Супер! Твоя жена на вершине счастья!"

    # Эмодзи для здоровья
    if health_int <= 3:
        health_emoji = "🤕"
    elif health_int <= 6:
        health_emoji = "😐"
    elif health_int <= 8:
        health_emoji = "💪"
    else:
        health_emoji = "🌟"

    message = f"📊 Состояние {wife_name}:\n\n"
    message += f"{mood_emoji} Настроение: {mood_int}/10\n"
    message += f"{health_emoji} Здоровье: {health_int}/10\n\n"
    message += advice

    await update.message.reply_text(message, reply_markup=husband_main_kb())


def get_last_wife_status(family_key):
    """Возвращает последнее настроение и здоровье жены"""
    try:
        if os.path.exists(WOMEN_FILE):
            df = pd.read_csv(WOMEN_FILE)
            family_records = df[df['family_key'] == str(family_key)]

            if not family_records.empty:
                latest = family_records.iloc[-1]
                return {
                    'mood': str(latest['mood']),
                    'health': str(latest['health'])
                }
    except Exception as e:
        print(f"❌ Ошибка при получении статуса: {e}")

    return {'mood': "Нет данных", 'health': "Нет данных"}


async def handle_mood_rating(update, context):
    """Обрабатывает ввод оценок настроения"""
    waiting_for = context.user_data.get('waiting_for')
    text = update.message.text.strip()

    if text == "🚫 Отмена":
        await cancel_mood_recording(update, context)
        return

    if waiting_for == 'mood':
        if not text.isdigit() or not (1 <= int(text) <= 10):
            await update.message.reply_text("⚠️ Выбери число от 1 до 10!", reply_markup=numbers_kb())
            return

        context.user_data['mood'] = text
        context.user_data['waiting_for'] = 'health'

        await update.message.reply_text(
            "✅ Записано!\n\n"
            "💪 А как здоровье от 1 до 10?\n"
            "1 - Плохо\n10 - Отлично!",
            reply_markup=numbers_kb()
        )

    elif waiting_for == 'health':
        mood = context.user_data.get('mood', '')

        if not text.isdigit() or not (1 <= int(text) <= 10):
            await update.message.reply_text("⚠️ Выбери число от 1 до 10!", reply_markup=numbers_kb())
            return

        health = text

        # Сохранение настроения
        success = save_mood_record(
            user_id=update.effective_user.id,
            family_key=context.user_data['family_key'],
            mood=mood,
            health=health
        )

        if success:
            # Формирование ответа
            mood_int = int(mood)
            health_int = int(health)

            if mood_int >= 8 and health_int >= 8:
                response = "🌟 Супер! Отличное настроение и здоровье!"
            elif mood_int >= 6 and health_int >= 6:
                response = "😊 Хорошо! Все в порядке!"
            else:
                response = "💖 Спасибо, что поделилась! Заботься о себе!"

            await update.message.reply_text(
                f"✅ Состояние сохранено!\n\n"
                f"😊 Настроение: {mood}/10\n"
                f"💪 Здоровье: {health}/10\n\n"
                f"{response}",
                reply_markup=wife_main_kb()
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось сохранить состояние",
                reply_markup=wife_main_kb()
            )

        # Очистка временных данных
        for key in ['mood', 'health', 'waiting_for']:
            context.user_data.pop(key, None)


async def cancel_mood_recording(update, context):
    """Отменяет запись настроения"""
    for key in ['mood', 'health', 'waiting_for']:
        context.user_data.pop(key, None)

    await update.message.reply_text(
        "📝 Запись настроения отменена",
        reply_markup=wife_main_kb()
    )