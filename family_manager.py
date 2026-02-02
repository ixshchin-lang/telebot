from config import *
import pandas as pd


async def create_family(update, context):
    """Процесс создания новой семьи"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Начало создания семьи
    if text == "🤝 Создать семью":
        family_dialogs[user_id] = {'step': 'wait_wife'}
        await update.message.reply_text("👰 Как зовут твою прекрасную жену?")
        return True

    # Если пользователь не в процессе создания семьи
    if user_id not in family_dialogs:
        return False

    state = family_dialogs[user_id]

    # Шаг 1: Получение имени жены
    if state['step'] == 'wait_wife':
        if len(text) < 2:
            await update.message.reply_text("⚠️ Дорогой, имя должно быть хотя бы 2 символа!")
            return True

        state['wife'] = text
        state['step'] = 'wait_husband'
        await update.message.reply_text(f"✅ Жена: {text}\n🤵 А как зовут тебя, герой?")

    # Шаг 2: Получение имени мужа и сохранение семьи
    elif state['step'] == 'wait_husband':
        if len(text) < 2:
            await update.message.reply_text("⚠️ Имя должно быть хотя бы 2 символа, мужик!")
            return True

        wife = state['wife']
        husband = text
        key = generate_key(wife, husband)

        # Создание записи о семье
        new_family = {
            'women': wife,
            'men': husband,
            'key': key,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # Чтение и добавление новой семьи
            if os.path.exists(FAMILY_FILE):
                df = pd.read_csv(FAMILY_FILE)
                df = pd.concat([df, pd.DataFrame([new_family])], ignore_index=True)
            else:
                df = pd.DataFrame([new_family])

            df.to_csv(FAMILY_FILE, index=False)

            # Очистка состояния диалога
            del family_dialogs[user_id]

            # Сохранение данных пользователя
            context.user_data.update({
                'family_key': key,
                'wife_name': wife,
                'husband_name': husband,
                'user_role': 'husband'  # Создатель становится мужем
            })

            await update.message.reply_text(
                f"🎉 Семья создана! Любовь и радость!\n\n"
                f"👰 {wife} + 🤵 {husband}\n\n"
                f"🔑 Твой ключ: <code>{key}</code>\n\n"
                f"⚠️ Запомни этот код! Поделись с женой для входа.",
                parse_mode='HTML',
                reply_markup=main_kb()
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при создании семьи: {e}")
            del family_dialogs[user_id]

    return True