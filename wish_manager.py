from config import *
import pandas as pd
from datetime import datetime


def generate_wish_id():
    """Генерирует уникальный ID для желания"""
    return int(datetime.now().timestamp() * 1000)


async def start_add_wish(update, context):
    """Начинает процесс добавления нового желания"""
    await update.message.reply_text(
        "💭 О чем мечтаешь?",
        reply_markup=wish_type_kb()
    )


async def handle_wish_type(update, context):
    """Обрабатывает выбор типа желания"""
    text = update.message.text.strip()
    user_role = context.user_data.get('user_role', '')

    if text == "⬅️ Назад":
        kb = husband_main_kb() if user_role == 'husband' else wife_main_kb()
        await update.message.reply_text("Главное меню:", reply_markup=kb)
        return

    if text == "✨ Моральное":
        context.user_data['wish_type'] = 'Моральное'
        context.user_data['wish_step'] = 'title'
        await update.message.reply_text(
            "✨ Опиши свое желание:\n(Например: 'Романтический вечер')",
            reply_markup=back_only_kb()
        )
    elif text == "🛍️ Покупка":
        context.user_data['wish_type'] = 'Покупка'
        context.user_data['wish_step'] = 'title'
        await update.message.reply_text(
            "🛍️ Что хочешь купить?\n(Например: 'Новое платье')",
            reply_markup=back_only_kb()
        )


async def save_wish(update, context):
    """Сохраняет желание в базу данных"""
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Обработка кнопки Назад
    if text == "⬅️ Назад":
        await handle_back_in_wish(update, context)
        return

    family_key = context.user_data.get('family_key')
    user_role = context.user_data.get('user_role', '')
    wish_step = context.user_data.get('wish_step', '')

    if not family_key:
        await update.message.reply_text("❌ Нет доступа к семье")
        return

    if wish_step == 'title':
        if len(text) < 3:
            await update.message.reply_text("⚠️ Опиши подробнее! Минимум 3 символа.")
            return

        context.user_data['wish_title'] = text

        if context.user_data['wish_type'] == 'Покупка':
            context.user_data['wish_step'] = 'price'
            await update.message.reply_text(
                "💰 На какую сумму рассчитываешь? (в рублях)",
                reply_markup=back_only_kb()
            )
        else:
            context.user_data['wish_step'] = 'mood'
            await update.message.reply_text(
                "😊 Насколько поднимется настроение? (1-10)",
                reply_markup=numbers_kb()
            )

    elif wish_step == 'price':
        try:
            price = float(text)
            if price <= 0:
                await update.message.reply_text("⚠️ Цена должна быть положительной!")
                return

            context.user_data['wish_price'] = price
            context.user_data['wish_step'] = 'mood'

            await update.message.reply_text(
                "😊 Насколько поднимется настроение? (1-10)",
                reply_markup=numbers_kb()
            )
        except ValueError:
            await update.message.reply_text("⚠️ Введи число! Например: 1500")

    elif wish_step == 'mood':
        if text == "🚫 Отмена":
            context.user_data['wish_step'] = 'title'
            await update.message.reply_text(
                "✨ Опиши свое желание:",
                reply_markup=back_only_kb()
            )
            return

        if text.isdigit() and 1 <= int(text) <= 10:
            await finalize_wish_saving(update, context, int(text))
        else:
            await update.message.reply_text("⚠️ Выбери от 1 до 10!", reply_markup=numbers_kb())


async def handle_back_in_wish(update, context):
    """Обрабатывает кнопку Назад при добавлении желания"""
    wish_step = context.user_data.get('wish_step', '')
    user_role = context.user_data.get('user_role', '')

    if wish_step == 'title':
        await update.message.reply_text("💭 О чем мечтаешь?", reply_markup=wish_type_kb())
    elif wish_step == 'price':
        context.user_data['wish_step'] = 'title'
        await update.message.reply_text("✨ Опиши свое желание:", reply_markup=back_only_kb())
    else:
        kb = husband_main_kb() if user_role == 'husband' else wife_main_kb()
        await update.message.reply_text("Главное меню:", reply_markup=kb)


async def finalize_wish_saving(update, context, mood_value):
    """Завершает процесс сохранения желания"""
    user_id = update.effective_user.id
    family_key = context.user_data.get('family_key')
    user_role = context.user_data.get('user_role', '')

    wish_type = context.user_data.get('wish_type', '')
    title = context.user_data.get('wish_title', '')
    price = context.user_data.get('wish_price', 0) if wish_type == 'Покупка' else 0

    try:
        # Создание записи о желании
        record = {
            'id': generate_wish_id(),
            'family_key': str(family_key),
            'user_id': int(user_id),
            'user_role': str(user_role),
            'type': str(wish_type),
            'title': str(title),
            'price': float(price),
            'expected_mood': int(mood_value),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'is_done': False
        }

        # Сохранение в файл
        if os.path.exists(WISH_FILE) and os.path.getsize(WISH_FILE) > 0:
            df = pd.read_csv(WISH_FILE)
            df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        else:
            df = pd.DataFrame([record])

        df.to_csv(WISH_FILE, index=False)

        print(f"💾 СОХРАНЕНО ЖЕЛАНИЕ:")
        print(f"   Семья: {family_key}")
        print(f"   User ID: {user_id}")
        print(f"   Роль: {user_role}")
        print(f"   Тип: {wish_type}")
        print(f"   Название: {title}")

        # Формирование сообщения
        if user_role == 'husband':
            if wish_type == 'Покупка':
                message = f"✅ Записано!\n\n🛍️ {title}\n💰 {price} руб.\n😊 +{mood_value}/10 к настроению"
            else:
                message = f"✅ Записано!\n\n✨ {title}\n😊 +{mood_value}/10 к настроению"
        else:
            if wish_type == 'Покупка':
                message = f"✅ Записано!\n\n🛍️ {title}\n💰 {price} руб.\n😊 +{mood_value}/10 к настроению"
            else:
                message = f"✅ Записано!\n\n✨ {title}\n😊 +{mood_value}/10 к настроению"

        # Очистка данных
        for key in ['wish_type', 'wish_title', 'wish_price', 'wish_step']:
            context.user_data.pop(key, None)

        # Возврат в меню
        kb = husband_main_kb() if user_role == 'husband' else wife_main_kb()
        await update.message.reply_text(message, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        await update.message.reply_text(f"❌ Ошибка сохранения: {e}")


def get_wish_control_kb(wish_id, is_my_wish=True, current_page=0, total_pages=1, wish_type='my'):
    """Создает клавиатуру управления для желания"""
    buttons = []

    if is_my_wish:
        buttons.append([
            InlineKeyboardButton("✅ Выполнено", callback_data=f"done_{wish_id}"),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{wish_id}")
        ])

    # Кнопки навигации
    nav_buttons = []

    if current_page > 0:
        # Для моих желаний
        if wish_type == 'my':
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_my_{wish_id}_{current_page}"))
        else:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_spouse_{wish_id}_{current_page}"))

    # Кнопка с номером страницы
    nav_buttons.append(InlineKeyboardButton(f"{current_page + 1}/{total_pages}", callback_data="page_info"))

    if current_page < total_pages - 1:
        # Для моих желаний
        if wish_type == 'my':
            nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"next_my_{wish_id}_{current_page}"))
        else:
            nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"next_spouse_{wish_id}_{current_page}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)


async def show_my_wishes(update, context, page=0):
    """Показывает желания текущего пользователя"""
    # Определяем тип обновления
    if hasattr(update, 'callback_query') and update.callback_query:
        # Если это callback_query (нажата инлайн-кнопка)
        user_id = str(update.callback_query.from_user.id)
        message_obj = update.callback_query.message
        is_callback = True
    else:
        # Если это обычное сообщение (нажата кнопка меню)
        user_id = str(update.effective_user.id)
        message_obj = update.message
        is_callback = False

    family_key = str(context.user_data.get('family_key', ''))
    user_role = context.user_data.get('user_role', '')

    if not family_key:
        if not is_callback:
            await update.message.reply_text("❌ Нет доступа к семье")
        return

    try:
        if not os.path.exists(WISH_FILE) or os.path.getsize(WISH_FILE) == 0:
            if is_callback:
                await message_obj.edit_text("📭 Пока нет желаний, добавь первое!")
            else:
                await show_no_wishes_message(update, user_role)
            return

        df = pd.read_csv(WISH_FILE)

        # Преобразуем типы данных
        df['user_id'] = df['user_id'].astype(str)
        df['family_key'] = df['family_key'].astype(str)

        # Фильтрация МОИХ желаний (только не выполненные)
        my_wishes = df[
            (df['family_key'] == family_key) &
            (df['user_id'] == user_id) &
            (df['is_done'] == False)
            ]

        print(f"🔍 Найдено моих желаний: {len(my_wishes)}")

        if my_wishes.empty:
            if is_callback:
                await message_obj.edit_text("📭 Пока нет желаний, добавь первое!")
            else:
                await show_no_wishes_message(update, user_role)
            return

        # Сортировка по дате (новые сверху)
        my_wishes = my_wishes.sort_values('created_at', ascending=False).reset_index(drop=True)

        total = len(my_wishes)
        if page >= total:
            page = total - 1

        wish = my_wishes.iloc[page]

        # Формирование сообщения
        message = format_wish_message(wish, page, total, "⭐ Твое желание")

        # Создание клавиатуры
        keyboard = get_wish_control_kb(
            int(wish['id']),
            is_my_wish=True,
            current_page=page,
            total_pages=total,
            wish_type='my'
        )

        # Отправка/редактирование сообщения
        if is_callback:
            await message_obj.edit_text(message, reply_markup=keyboard)
        else:
            await message_obj.reply_text(message, reply_markup=keyboard)

        # Сохранение информации о пагинации
        wish_pagination[user_id] = {
            'wishes': my_wishes.to_dict('records'),
            'current_page': page,
            'type': 'my',
            'total': total
        }

    except Exception as e:
        print(f"❌ Ошибка при показе моих желаний: {e}")
        if is_callback:
            await message_obj.edit_text(f"❌ Ошибка: {e}")
        else:
            await show_no_wishes_message(update, user_role)


async def show_spouse_wishes(update, context, page=0):
    """Показывает желания супруга/супруги"""
    # Определяем тип обновления
    if hasattr(update, 'callback_query') and update.callback_query:
        # Если это callback_query (нажата инлайн-кнопка)
        user_id = str(update.callback_query.from_user.id)
        message_obj = update.callback_query.message
        is_callback = True
    else:
        # Если это обычное сообщение (нажата кнопка меню)
        user_id = str(update.effective_user.id)
        message_obj = update.message
        is_callback = False

    family_key = str(context.user_data.get('family_key', ''))
    user_role = context.user_data.get('user_role', '')

    if not family_key:
        if not is_callback:
            await update.message.reply_text("❌ Нет доступа к семье")
        return

    # Определение роли супруга
    spouse_role = 'wife' if user_role == 'husband' else 'husband'
    spouse_name = context.user_data.get('wife_name' if spouse_role == 'wife' else 'husband_name', 'супруга')

    try:
        if not os.path.exists(WISH_FILE) or os.path.getsize(WISH_FILE) == 0:
            if is_callback:
                await message_obj.edit_text(f"📭 У {spouse_name} пока нет желаний")
            else:
                await update.message.reply_text(
                    f"📭 У {spouse_name} пока нет желаний",
                    reply_markup=husband_main_kb() if user_role == 'husband' else wife_main_kb()
                )
            return

        df = pd.read_csv(WISH_FILE)

        # Преобразуем типы данных
        df['family_key'] = df['family_key'].astype(str)
        df['user_role'] = df['user_role'].astype(str)

        # Фильтрация желаний СУПРУГА (только не выполненные)
        spouse_wishes = df[
            (df['family_key'] == family_key) &
            (df['user_role'] == spouse_role) &
            (df['is_done'] == False)
            ]

        print(f"🔍 Найдено желаний супруга: {len(spouse_wishes)}")

        if spouse_wishes.empty:
            if is_callback:
                await message_obj.edit_text(f"📭 У {spouse_name} пока нет желаний")
            else:
                await update.message.reply_text(
                    f"📭 У {spouse_name} пока нет желаний",
                    reply_markup=husband_main_kb() if user_role == 'husband' else wife_main_kb()
                )
            return

        # Сортировка по дате (новые сверху)
        spouse_wishes = spouse_wishes.sort_values('created_at', ascending=False).reset_index(drop=True)

        total = len(spouse_wishes)
        if page >= total:
            page = total - 1

        wish = spouse_wishes.iloc[page]

        # Формирование сообщения
        title = "🤵 Муж" if spouse_role == 'husband' else "👰 Жена"
        message = format_wish_message(wish, page, total, f"💭 Желание {title}")

        # Создание клавиатуры (только для просмотра)
        keyboard = get_wish_control_kb(
            int(wish['id']),
            is_my_wish=False,
            current_page=page,
            total_pages=total,
            wish_type='spouse'
        )

        # Отправка/редактирование сообщения
        if is_callback:
            await message_obj.edit_text(message, reply_markup=keyboard)
        else:
            await message_obj.reply_text(message, reply_markup=keyboard)

        # Сохранение информации о пагинации
        wish_pagination[user_id] = {
            'wishes': spouse_wishes.to_dict('records'),
            'current_page': page,
            'type': 'spouse',
            'total': total
        }

    except Exception as e:
        print(f"❌ Ошибка при показе желаний супруга: {e}")
        if is_callback:
            await message_obj.edit_text(f"❌ Ошибка: {e}")
        else:
            kb = husband_main_kb() if user_role == 'husband' else wife_main_kb()
            await update.message.reply_text(
                f"📭 У {spouse_name} пока нет желаний",
                reply_markup=kb
            )


def format_wish_message(wish, page, total, prefix):
    """Форматирует сообщение о желании"""
    try:
        created = datetime.strptime(wish['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')

        message = f"{prefix} ({page + 1}/{total}):\n\n"

        if wish['type'] == 'Покупка':
            message += f"🛍️ {wish['title']}\n"
            message += f"💰 {wish['price']} руб.\n"
        else:
            message += f"✨ {wish['title']}\n"

        message += f"😊 +{wish['expected_mood']}/10 к настроению\n"
        message += f"📅 Добавлено: {created}"

        return message
    except Exception as e:
        print(f"❌ Ошибка при форматировании: {e}")
        return "📋 Информация о желании"


async def show_no_wishes_message(update, user_role):
    """Показывает сообщение об отсутствии желаний"""
    kb = husband_main_kb() if user_role == 'husband' else wife_main_kb()
    await update.message.reply_text(
        "📭 Пока нет желаний, добавь первое!",
        reply_markup=kb
    )


async def handle_wish_action(update, context):
    """Обрабатывает действия с желаниями (кнопки)"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = str(query.from_user.id)

    print(f"🔘 Нажата кнопка: {data}")

    # Разбор команды
    if data == "page_info":
        return  # Игнорируем кнопку информации о странице

    elif data.startswith('done_'):
        wish_id = int(data.split('_')[1])
        await mark_wish_done(wish_id, user_id, query, context)

    elif data.startswith('delete_'):
        wish_id = int(data.split('_')[1])
        await delete_wish(wish_id, user_id, query, context)

    elif data.startswith('next_my_'):
        # Формат: next_my_wishId_currentPage
        parts = data.split('_')
        if len(parts) >= 4:
            wish_id = int(parts[2])
            current_page = int(parts[3])
            await handle_next_wish(user_id, wish_id, current_page, query, context, 'my')

    elif data.startswith('prev_my_'):
        parts = data.split('_')
        if len(parts) >= 4:
            wish_id = int(parts[2])
            current_page = int(parts[3])
            await handle_prev_wish(user_id, wish_id, current_page, query, context, 'my')

    elif data.startswith('next_spouse_'):
        parts = data.split('_')
        if len(parts) >= 4:
            wish_id = int(parts[2])
            current_page = int(parts[3])
            await handle_next_wish(user_id, wish_id, current_page, query, context, 'spouse')

    elif data.startswith('prev_spouse_'):
        parts = data.split('_')
        if len(parts) >= 4:
            wish_id = int(parts[2])
            current_page = int(parts[3])
            await handle_prev_wish(user_id, wish_id, current_page, query, context, 'spouse')


async def handle_next_wish(user_id, wish_id, current_page, query, context, wish_type):
    """Обрабатывает кнопку "Вперед" """
    if user_id not in wish_pagination:
        return

    page_info = wish_pagination[user_id]
    total_pages = page_info['total']

    # Рассчитываем следующую страницу
    next_page = current_page + 1

    if next_page >= total_pages:
        next_page = 0  # Циклическая навигация

    print(f"📄 Переход на страницу {next_page + 1}/{total_pages}")

    # Показываем следующее желание
    if wish_type == 'my':
        # Создаем объект Update с callback_query
        class FakeUpdate:
            def __init__(self, callback_query):
                self.callback_query = callback_query

        fake_update = FakeUpdate(query)
        await show_my_wishes(fake_update, context, next_page)
    else:
        class FakeUpdate:
            def __init__(self, callback_query):
                self.callback_query = callback_query

        fake_update = FakeUpdate(query)
        await show_spouse_wishes(fake_update, context, next_page)


async def handle_prev_wish(user_id, wish_id, current_page, query, context, wish_type):
    """Обрабатывает кнопку "Назад" """
    if user_id not in wish_pagination:
        return

    page_info = wish_pagination[user_id]
    total_pages = page_info['total']

    # Рассчитываем предыдущую страницу
    prev_page = current_page - 1

    if prev_page < 0:
        prev_page = total_pages - 1  # Циклическая навигация

    print(f"📄 Переход на страницу {prev_page + 1}/{total_pages}")

    # Показываем предыдущее желание
    if wish_type == 'my':
        # Создаем объект Update с callback_query
        class FakeUpdate:
            def __init__(self, callback_query):
                self.callback_query = callback_query

        fake_update = FakeUpdate(query)
        await show_my_wishes(fake_update, context, prev_page)
    else:
        class FakeUpdate:
            def __init__(self, callback_query):
                self.callback_query = callback_query

        fake_update = FakeUpdate(query)
        await show_spouse_wishes(fake_update, context, prev_page)


async def mark_wish_done(wish_id, user_id, query, context):
    """Отмечает желание как выполненное"""
    try:
        if os.path.exists(WISH_FILE):
            df = pd.read_csv(WISH_FILE)
            df.loc[df['id'] == wish_id, 'is_done'] = True
            df.to_csv(WISH_FILE, index=False)

            await query.message.edit_text("✅ Готово! Желание выполнено! 🎉")

            # Обновить пагинацию и показать следующее желание
            if user_id in wish_pagination:
                page_info = wish_pagination[user_id]
                # Удалить выполненное желание из списка
                page_info['wishes'] = [w for w in page_info['wishes'] if w['id'] != wish_id]
                page_info['total'] = len(page_info['wishes'])

                if page_info['total'] == 0:
                    await query.message.edit_text("🎉 Все желания выполнены!")
                    return

                # Корректировка текущей страницы
                if page_info['current_page'] >= page_info['total']:
                    page_info['current_page'] = page_info['total'] - 1

                if page_info['type'] == 'my':
                    class FakeUpdate:
                        def __init__(self, callback_query):
                            self.callback_query = callback_query

                    fake_update = FakeUpdate(query)
                    await show_my_wishes(fake_update, context, page_info['current_page'])
                else:
                    class FakeUpdate:
                        def __init__(self, callback_query):
                            self.callback_query = callback_query

                    fake_update = FakeUpdate(query)
                    await show_spouse_wishes(fake_update, context, page_info['current_page'])
    except Exception as e:
        print(f"❌ Ошибка при выполнении желания: {e}")
        await query.message.edit_text(f"❌ Ошибка: {e}")


async def delete_wish(wish_id, user_id, query, context):
    """Удаляет желание из базы"""
    try:
        if os.path.exists(WISH_FILE):
            df = pd.read_csv(WISH_FILE)
            df = df[df['id'] != wish_id]
            df.to_csv(WISH_FILE, index=False)

            await query.message.edit_text("🗑️ Желание удалено!")

            # Обновить пагинацию и показать следующее желание
            if user_id in wish_pagination:
                page_info = wish_pagination[user_id]
                # Удалить желание из списка
                page_info['wishes'] = [w for w in page_info['wishes'] if w['id'] != wish_id]
                page_info['total'] = len(page_info['wishes'])

                if page_info['total'] == 0:
                    await query.message.edit_text("🗑️ Все желания удалены!")
                    return

                # Корректировка текущей страницы
                if page_info['current_page'] >= page_info['total']:
                    page_info['current_page'] = page_info['total'] - 1

                if page_info['type'] == 'my':
                    class FakeUpdate:
                        def __init__(self, callback_query):
                            self.callback_query = callback_query

                    fake_update = FakeUpdate(query)
                    await show_my_wishes(fake_update, context, page_info['current_page'])
                else:
                    class FakeUpdate:
                        def __init__(self, callback_query):
                            self.callback_query = callback_query

                    fake_update = FakeUpdate(query)
                    await show_spouse_wishes(fake_update, context, page_info['current_page'])
    except Exception as e:
        print(f"❌ Ошибка при удалении желания: {e}")
        await query.message.edit_text(f"❌ Ошибка: {e}")