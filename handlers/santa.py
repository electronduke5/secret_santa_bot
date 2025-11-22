from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import database as db
import keyboards as kb

router = Router()


@router.callback_query(F.data.startswith("start_distribution_"))
async def start_distribution_confirm(callback: CallbackQuery):
    """Подтверждение начала распределения"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if group["admin_id"] != callback.from_user.id:
        await callback.answer("❌ Только администратор может начать распределение", show_alert=True)
        return

    participants_count = len(group["participants"])

    if participants_count < 3:
        await callback.answer(
            f"❌ Недостаточно участников для распределения.\n"
            f"Минимум: 3\n"
            f"Текущее количество: {participants_count}",
            show_alert=True
        )
        return

    try:
        await callback.message.edit_text(
            f"🎲 <b>Начать распределение?</b>\n\n"
            f"📝 Группа: {group['name']}\n"
            f"👥 Участников: {participants_count}\n\n"
            f"⚠️ <b>Внимание!</b> После распределения:\n"
            f"• Нельзя будет добавить новых участников\n"
            f"• Каждый участник получит сообщение с именем того, кому нужно подарить подарок\n"
            f"• Вы можете отменить распределение и сделать его заново\n\n"
            f"Вы уверены?",
            reply_markup=kb.confirm_distribution(invite_code),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer()


@router.callback_query(F.data.startswith("confirm_dist_"))
async def confirm_distribution(callback: CallbackQuery):
    """Подтверждение и выполнение распределения"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if group["admin_id"] != callback.from_user.id:
        await callback.answer("❌ Только администратор может начать распределение", show_alert=True)
        return

    # Выполняем распределение
    success = db.distribute_santa(invite_code)

    if not success:
        await callback.answer("❌ Ошибка при распределении", show_alert=True)
        return

    # Получаем обновлённые данные группы
    group = db.get_group(invite_code)

    # Отправляем уведомления всем участникам
    bot: Bot = callback.bot
    success_count = 0
    failed_users = []

    for giver_id, assignment in group["assignments"].items():
        giver_info = group["participants"][giver_id]
        try:
            # Обратная совместимость: если assignment это строка (старый формат)
            if isinstance(assignment, str):
                receiver_id = assignment
            else:
                receiver_id = assignment["receiver_id"]

            recipient_info = group["participants"][receiver_id]

            username_text = f"@{recipient_info['username']}" if recipient_info['username'] else ""
            wishlist_text = f"\n\n🎁 <b>Пожелания:</b>\n{recipient_info['wishlist']}" if recipient_info['wishlist'] else "\n\n(Список пожеланий пока не указан)"

            await bot.send_message(
                chat_id=int(giver_id),
                text=f"🎅 <b>Распределение в группе \"{group['name']}\" завершено!</b>\n\n"
                     f"🎁 Вы дарите подарок:\n"
                     f"👤 <b>{recipient_info['first_name']}</b> {username_text}"
                     f"{wishlist_text}\n\n"
                     f"Сохраните эту информацию в секрете! 🤫",
                parse_mode="HTML"
            )
            success_count += 1
        except Exception as e:
            failed_users.append(giver_info['first_name'])
            print(f"Не удалось отправить сообщение пользователю {giver_id}: {e}")

    # Информируем админа о результатах
    result_text = f"✅ <b>Распределение завершено!</b>\n\n" \
                  f"📊 Уведомления отправлены: {success_count}/{len(group['assignments'])}\n"

    if failed_users:
        result_text += f"\n⚠️ Не удалось отправить сообщения:\n" + "\n".join([f"• {name}" for name in failed_users])
        result_text += "\n\nПопросите этих участников написать боту /start"

    # Получаем информацию о QR-кодах для админа
    has_qr_code = db.has_qr_code(invite_code, callback.from_user.id)
    qr_path = db.get_qr_code_for_recipient(invite_code, callback.from_user.id)
    recipient_has_qr = qr_path is not None

    try:
        await callback.message.edit_text(
            result_text,
            reply_markup=kb.group_info_keyboard(
                invite_code,
                is_admin=True,
                is_distributed=True,
                user_id=callback.from_user.id,
                has_qr_code=has_qr_code,
                recipient_has_qr=recipient_has_qr
            ),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("🎉 Распределение завершено!")


@router.callback_query(F.data.startswith("cancel_distribution_"))
async def cancel_distribution(callback: CallbackQuery):
    """Отмена распределения"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if group["admin_id"] != callback.from_user.id:
        await callback.answer("❌ Только администратор может отменить распределение", show_alert=True)
        return

    # Отменяем распределение
    db.cancel_distribution(invite_code)

    try:
        await callback.message.edit_text(
            f"🔄 <b>Распределение отменено</b>\n\n"
            f"Вы можете запустить распределение заново.",
            reply_markup=kb.group_info_keyboard(
                invite_code,
                is_admin=True,
                is_distributed=False,
                user_id=callback.from_user.id
            ),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("✅ Распределение отменено")


@router.callback_query(F.data.startswith("my_recipient_"))
async def show_my_recipient(callback: CallbackQuery):
    """Показать информацию о получателе подарка"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if not group["is_distributed"]:
        await callback.answer("❌ Распределение ещё не началось", show_alert=True)
        return

    recipient = db.get_recipient(callback.from_user.id, invite_code)

    if not recipient:
        await callback.answer("❌ Информация о получателе не найдена", show_alert=True)
        return

    username_text = f"@{recipient['username']}" if recipient['username'] else ""
    wishlist_text = f"\n\n🎁 Пожелания:\n{recipient['wishlist']}" if recipient['wishlist'] else "\n\n(Список пожеланий не указан)"

    await callback.answer(
        f"🎁 Вы дарите подарок:\n\n"
        f"👤 {recipient['first_name']} {username_text}"
        f"{wishlist_text}\n\n"
        f"🤫 Держите это в секрете!",
        show_alert=True
    )
