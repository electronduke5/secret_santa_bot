from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
import database as db
import keyboards as kb

router = Router()


class CreateGroupStates(StatesGroup):
    waiting_for_name = State()


class JoinGroupStates(StatesGroup):
    waiting_for_code = State()


class WishlistStates(StatesGroup):
    waiting_for_wishlist = State()
    group_code = State()


# Создание группы
@router.callback_query(F.data == "create_group")
async def create_group_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания группы"""
    try:
        await callback.message.edit_text(
            "🎅 <b>Создание новой группы</b>\n\n"
            "Введите название группы для Тайного Санты:\n"
            "(например: <i>Офисный Санта 2025</i>)",
            reply_markup=kb.cancel_action("back_to_menu"),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await state.set_state(CreateGroupStates.waiting_for_name)
    await callback.answer()


@router.message(CreateGroupStates.waiting_for_name)
async def create_group_finish(message: Message, state: FSMContext):
    """Завершение создания группы"""
    group_name = message.text.strip()

    if len(group_name) < 3:
        await message.answer(
            "❌ Название группы слишком короткое. Введите минимум 3 символа:",
            reply_markup=kb.cancel_action("back_to_menu")
        )
        return

    # Создаём группу
    invite_code = db.create_group(
        admin_id=message.from_user.id,
        admin_name=message.from_user.first_name,
        admin_username=message.from_user.username,
        group_name=group_name
    )

    await message.answer(
        f"✅ <b>Группа создана!</b>\n\n"
        f"📝 Название: {group_name}\n"
        f"👤 Администратор: {message.from_user.first_name}\n\n"
        f"🔗 <b>Пригласительный код:</b> <code>{invite_code}</code>\n\n"
        f"Отправьте этот код друзьям, чтобы они могли присоединиться к группе!",
        reply_markup=kb.main_menu(),
        parse_mode="HTML"
    )

    await state.clear()


# Присоединение к группе
@router.callback_query(F.data == "join_group")
async def join_group_start(callback: CallbackQuery, state: FSMContext):
    """Начало присоединения к группе"""
    try:
        await callback.message.edit_text(
            "👥 <b>Присоединиться к группе</b>\n\n"
            "Введите пригласительный код, который вам отправил администратор группы:",
            reply_markup=kb.cancel_action("back_to_menu"),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await state.set_state(JoinGroupStates.waiting_for_code)
    await callback.answer()


@router.message(JoinGroupStates.waiting_for_code)
async def join_group_finish(message: Message, state: FSMContext):
    """Завершение присоединения к группе"""
    invite_code = message.text.strip().lower()

    # Проверяем существование группы
    group = db.get_group(invite_code)
    if not group:
        await message.answer(
            "❌ Группа с таким кодом не найдена. Проверьте код и попробуйте снова:",
            reply_markup=kb.cancel_action("back_to_menu")
        )
        return

    # Проверяем, не является ли пользователь уже участником
    if str(message.from_user.id) in group["participants"]:
        await message.answer(
            f"ℹ️ Вы уже состоите в группе <b>{group['name']}</b>",
            reply_markup=kb.main_menu(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Присоединяемся к группе
    success = db.join_group(
        invite_code=invite_code,
        user_id=message.from_user.id,
        user_name=message.from_user.first_name,
        username=message.from_user.username
    )

    if success:
        await message.answer(
            f"✅ <b>Вы присоединились к группе!</b>\n\n"
            f"📝 Название: {group['name']}\n"
            f"👥 Участников: {len(group['participants']) + 1}\n\n"
            f"Дождитесь, пока администратор запустит распределение участников.",
            reply_markup=kb.main_menu(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось присоединиться к группе. Возможно, распределение уже началось.",
            reply_markup=kb.main_menu()
        )

    await state.clear()


# Мои группы
@router.callback_query(F.data == "my_groups")
async def show_my_groups(callback: CallbackQuery):
    """Показать список групп пользователя"""
    groups = db.get_user_groups(callback.from_user.id)

    try:
        if not groups:
            await callback.message.edit_text(
                "📭 <b>У вас пока нет групп</b>\n\n"
                "Создайте новую группу или присоединитесь к существующей!",
                reply_markup=kb.main_menu(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"👥 <b>Ваши группы ({len(groups)}):</b>\n\n"
                "Выберите группу для просмотра:",
                reply_markup=kb.group_list_keyboard(groups),
                parse_mode="HTML"
            )
    except TelegramBadRequest as e:
        # Игнорируем ошибку если сообщение не изменилось
        if "message is not modified" not in str(e):
            raise

    await callback.answer()


# Информация о группе
@router.callback_query(F.data.startswith("group_info_"))
async def show_group_info(callback: CallbackQuery):
    """Показать информацию о группе"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    is_admin = group["admin_id"] == callback.from_user.id
    admin_label = "👑" if is_admin else ""

    status = "✅ Распределение завершено" if group["is_distributed"] else "⏳ Ожидание начала"

    # Проверяем наличие QR-кодов
    has_qr_code = False
    recipient_has_qr = False
    if group["is_distributed"]:
        has_qr_code = db.has_qr_code(invite_code, callback.from_user.id)
        qr_path = db.get_qr_code_for_recipient(invite_code, callback.from_user.id)
        recipient_has_qr = qr_path is not None

    try:
        await callback.message.edit_text(
            f"📝 <b>{group['name']}</b> {admin_label}\n\n"
            f"👥 Участников: {len(group['participants'])}\n"
            f"📊 Статус: {status}\n"
            f"🔗 Код приглашения: <code>{invite_code}</code>\n\n"
            f"Выберите действие:",
            reply_markup=kb.group_info_keyboard(
                invite_code,
                is_admin,
                group["is_distributed"],
                user_id=callback.from_user.id,
                has_qr_code=has_qr_code,
                recipient_has_qr=recipient_has_qr
            ),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        # Игнорируем ошибку если сообщение не изменилось
        if "message is not modified" not in str(e):
            raise

    await callback.answer()


# Список участников
@router.callback_query(F.data.startswith("participants_"))
async def show_participants(callback: CallbackQuery):
    """Показать список участников группы"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    participants_list = []
    for user_id, user_info in group["participants"].items():
        is_admin = int(user_id) == group["admin_id"]
        admin_mark = "👑 " if is_admin else ""
        username = f"@{user_info['username']}" if user_info['username'] else ""

        participants_list.append(
            f"{admin_mark}{user_info['first_name']} {username}"
        )

    await callback.answer(
        f"👥 Участники ({len(participants_list)}):\n\n" + "\n".join(participants_list),
        show_alert=True
    )


# Пригласительная ссылка (только для админа)
@router.callback_query(F.data.startswith("invite_link_"))
async def show_invite_link(callback: CallbackQuery):
    """Показать пригласительный код"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if group["admin_id"] != callback.from_user.id:
        await callback.answer("❌ Только администратор может видеть эту информацию", show_alert=True)
        return

    bot_username = (await callback.bot.me()).username
    invite_link = f"https://t.me/{bot_username}?start={invite_code}"

    await callback.answer(
        f"🔗 Пригласительный код: {invite_code}\n\n"
        f"Отправьте код или ссылку друзьям:\n{invite_link}",
        show_alert=True
    )


# Установка списка пожеланий
@router.callback_query(F.data.startswith("set_wishlist_"))
async def set_wishlist_start(callback: CallbackQuery, state: FSMContext):
    """Начало установки списка пожеланий"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    # Получаем текущий список пожеланий
    current_wishlist = db.get_wishlist(callback.from_user.id, invite_code)
    current_text = f"\n\n<b>Текущий список:</b>\n{current_wishlist}" if current_wishlist else ""

    try:
        await callback.message.edit_text(
            f"🎁 <b>Список пожеланий</b>\n\n"
            f"Введите ваши пожелания к подарку (например: книги, чай, сладости){current_text}\n\n"
            f"Этот список увидит тот, кто будет дарить вам подарок.",
            reply_markup=kb.cancel_action(f"group_info_{invite_code}"),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await state.update_data(group_code=invite_code)
    await state.set_state(WishlistStates.waiting_for_wishlist)
    await callback.answer()


@router.message(WishlistStates.waiting_for_wishlist)
async def set_wishlist_finish(message: Message, state: FSMContext):
    """Завершение установки списка пожеланий"""
    data = await state.get_data()
    invite_code = data.get("group_code")

    wishlist = message.text.strip()

    if len(wishlist) > 500:
        await message.answer(
            "❌ Список пожеланий слишком длинный. Максимум 500 символов.",
            reply_markup=kb.cancel_action(f"group_info_{invite_code}")
        )
        return

    success = db.set_wishlist(message.from_user.id, invite_code, wishlist)

    if success:
        group = db.get_group(invite_code)
        has_qr_code = False
        recipient_has_qr = False
        if group["is_distributed"]:
            has_qr_code = db.has_qr_code(invite_code, message.from_user.id)
            qr_path = db.get_qr_code_for_recipient(invite_code, message.from_user.id)
            recipient_has_qr = qr_path is not None

        await message.answer(
            f"✅ <b>Список пожеланий сохранён!</b>\n\n"
            f"🎁 Ваши пожелания:\n{wishlist}",
            reply_markup=kb.group_info_keyboard(
                invite_code,
                is_admin=False,
                is_distributed=group["is_distributed"],
                user_id=message.from_user.id,
                has_qr_code=has_qr_code,
                recipient_has_qr=recipient_has_qr
            ),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось сохранить список пожеланий.",
            reply_markup=kb.main_menu()
        )

    await state.clear()


# Удаление группы
@router.callback_query(F.data.startswith("delete_group_"))
async def delete_group_confirm(callback: CallbackQuery):
    """Подтверждение удаления группы"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if group["admin_id"] != callback.from_user.id:
        await callback.answer("❌ Только администратор может удалить группу", show_alert=True)
        return

    participants_count = len(group["participants"])
    qr_count = 0

    # Подсчитываем количество загруженных QR-кодов
    if group.get("is_distributed") and group.get("assignments"):
        for assignment in group["assignments"].values():
            if isinstance(assignment, dict) and assignment.get("qr_code_path"):
                qr_count += 1

    await callback.message.edit_text(
        f"⚠️ <b>Удаление группы</b>\n\n"
        f"📝 Группа: <b>{group['name']}</b>\n"
        f"👥 Участников: {participants_count}\n"
        f"📊 Статус: {'✅ Распределено' if group['is_distributed'] else '⏳ Не распределено'}\n"
        f"📱 QR-кодов загружено: {qr_count}\n\n"
        f"🚨 <b>ВНИМАНИЕ!</b> Это действие необратимо!\n\n"
        f"Будут удалены:\n"
        f"• Вся информация о группе\n"
        f"• Список участников\n"
        f"• Все распределения\n"
        f"• Все загруженные QR-коды\n"
        f"• Списки пожеланий\n\n"
        f"Вы уверены, что хотите удалить эту группу?",
        reply_markup=kb.confirm_delete_group(invite_code),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_group_execute(callback: CallbackQuery):
    """Выполнение удаления группы"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if group["admin_id"] != callback.from_user.id:
        await callback.answer("❌ Только администратор может удалить группу", show_alert=True)
        return

    group_name = group["name"]

    # Удаляем группу
    success = db.delete_group(invite_code)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Группа удалена</b>\n\n"
            f"Группа <b>\"{group_name}\"</b> успешно удалена.\n"
            f"Все связанные данные и QR-коды были удалены.",
            reply_markup=kb.main_menu(),
            parse_mode="HTML"
        )
        await callback.answer("✅ Группа удалена")
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении группы</b>\n\n"
            f"Не удалось удалить группу. Попробуйте позже.",
            reply_markup=kb.main_menu(),
            parse_mode="HTML"
        )
        await callback.answer("❌ Ошибка удаления", show_alert=True)
