from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
import database as db
import keyboards as kb
import os

router = Router()

QR_CODES_DIR = "qr_codes"


class UploadQRStates(StatesGroup):
    waiting_for_photo = State()
    group_code = State()


@router.callback_query(F.data.startswith("upload_qr_"))
async def upload_qr_start(callback: CallbackQuery, state: FSMContext):
    """Начало загрузки QR-кода дарителем"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if not group["is_distributed"]:
        await callback.answer("❌ Распределение ещё не началось", show_alert=True)
        return

    # Проверяем что пользователь является участником
    recipient = db.get_recipient(callback.from_user.id, invite_code)
    if not recipient:
        await callback.answer("❌ Вы не участвуете в этой группе", show_alert=True)
        return

    # Проверяем есть ли уже загруженный QR-код
    has_qr = db.has_qr_code(invite_code, callback.from_user.id)
    action_text = "заменить" if has_qr else "загрузить"

    try:
        await callback.message.edit_text(
            f"📤 <b>Загрузка QR-кода</b>\n\n"
            f"Отправьте фото QR-кода для получения подарка в пункте выдачи заказов.\n\n"
            f"Этот QR-код будет доступен получателю вашего подарка.\n\n"
            f"{'⚠️ Внимание: текущий QR-код будет заменён новым.' if has_qr else ''}",
            reply_markup=kb.cancel_action(f"group_info_{invite_code}"),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await state.update_data(group_code=invite_code)
    await state.set_state(UploadQRStates.waiting_for_photo)
    await callback.answer()


@router.message(UploadQRStates.waiting_for_photo, F.photo)
async def upload_qr_photo(message: Message, state: FSMContext, bot: Bot):
    """Обработка загруженного фото QR-кода"""
    data = await state.get_data()
    invite_code = data.get("group_code")

    if not invite_code:
        await message.answer("❌ Ошибка: код группы не найден")
        await state.clear()
        return

    group = db.get_group(invite_code)
    if not group:
        await message.answer("❌ Группа не найдена")
        await state.clear()
        return

    try:
        # Получаем фото (берем самое качественное - последнее в списке)
        photo = message.photo[-1]

        # Создаём имя файла
        file_name = f"{invite_code}_{message.from_user.id}.jpg"
        file_path = os.path.join(QR_CODES_DIR, file_name)

        # Проверяем существует ли старый QR-код и удаляем его
        old_qr_path = None
        if db.has_qr_code(invite_code, message.from_user.id):
            recipient = db.get_recipient(message.from_user.id, invite_code)
            if recipient and recipient.get("qr_code_path"):
                old_qr_path = recipient["qr_code_path"]

        # Скачиваем файл
        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, file_path)

        # Удаляем старый QR-код если был
        if old_qr_path and old_qr_path != file_path:
            db.delete_qr_code_file(old_qr_path)

        # Сохраняем путь к файлу в базе данных
        success = db.save_qr_code_path(invite_code, message.from_user.id, file_path)

        if success:
            # Отправляем уведомление получателю подарка
            try:
                assignment = group["assignments"][str(message.from_user.id)]

                # Обратная совместимость: если assignment это строка (старый формат)
                if isinstance(assignment, str):
                    receiver_id = assignment
                else:
                    receiver_id = assignment["receiver_id"]

                receiver_info = group["participants"][receiver_id]

                await bot.send_message(
                    chat_id=int(receiver_id),
                    text=f"🔔 <b>Уведомление</b>\n\n"
                         f"В группе <b>\"{group['name']}\"</b> ваш Тайный Санта загрузил QR-код!\n\n"
                         f"📱 Теперь вы можете посмотреть QR-код для получения подарка в пункте выдачи.",
                    reply_markup=kb.group_info_keyboard(
                        invite_code,
                        is_admin=group["admin_id"] == int(receiver_id),
                        is_distributed=True,
                        user_id=int(receiver_id),
                        has_qr_code=db.has_qr_code(invite_code, int(receiver_id)),
                        recipient_has_qr=True
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление получателю: {e}")

            # Проверяем информацию о QR-кодах для кнопок
            has_qr_code = db.has_qr_code(invite_code, message.from_user.id)
            qr_path = db.get_qr_code_for_recipient(invite_code, message.from_user.id)
            recipient_has_qr = qr_path is not None

            await message.answer(
                f"✅ <b>QR-код успешно загружен!</b>\n\n"
                f"Получатель вашего подарка сможет использовать этот QR-код для получения посылки в ПВЗ.",
                reply_markup=kb.group_info_keyboard(
                    invite_code,
                    is_admin=group["admin_id"] == message.from_user.id,
                    is_distributed=True,
                    user_id=message.from_user.id,
                    has_qr_code=has_qr_code,
                    recipient_has_qr=recipient_has_qr
                ),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при сохранении QR-кода. Попробуйте позже.",
                reply_markup=kb.main_menu()
            )

    except Exception as e:
        print(f"Ошибка при загрузке QR-кода: {e}")

        # Проверяем информацию о QR-кодах для кнопок
        has_qr_code = db.has_qr_code(invite_code, message.from_user.id)
        qr_path = db.get_qr_code_for_recipient(invite_code, message.from_user.id)
        recipient_has_qr = qr_path is not None

        await message.answer(
            "❌ Ошибка при загрузке QR-кода. Попробуйте ещё раз.",
            reply_markup=kb.group_info_keyboard(
                invite_code,
                is_admin=group["admin_id"] == message.from_user.id,
                is_distributed=True,
                user_id=message.from_user.id,
                has_qr_code=has_qr_code,
                recipient_has_qr=recipient_has_qr
            )
        )

    await state.clear()


@router.message(UploadQRStates.waiting_for_photo)
async def upload_qr_invalid(message: Message, state: FSMContext):
    """Обработка неправильного типа сообщения"""
    data = await state.get_data()
    invite_code = data.get("group_code")

    await message.answer(
        "❌ Пожалуйста, отправьте фото QR-кода.\n\n"
        "Убедитесь, что вы отправляете изображение, а не файл.",
        reply_markup=kb.cancel_action(f"group_info_{invite_code}")
    )


@router.callback_query(F.data.startswith("view_qr_"))
async def view_qr_code(callback: CallbackQuery):
    """Просмотр QR-кода получателем"""
    invite_code = callback.data.split("_")[-1]
    group = db.get_group(invite_code)

    if not group:
        await callback.answer("❌ Группа не найдена", show_alert=True)
        return

    if not group["is_distributed"]:
        await callback.answer("❌ Распределение ещё не началось", show_alert=True)
        return

    # Получаем QR-код (находим кто дарит подарок этому пользователю)
    qr_code_path = db.get_qr_code_for_recipient(invite_code, callback.from_user.id)

    if not qr_code_path:
        await callback.answer(
            "❌ QR-код ещё не загружен вашим Тайным Сантой.\n\n"
            "Подождите, пока даритель загрузит QR-код.",
            show_alert=True
        )
        return

    # Проверяем существует ли файл
    if not os.path.exists(qr_code_path):
        await callback.answer("❌ Файл QR-кода не найден", show_alert=True)
        return

    try:
        # Отправляем фото с QR-кодом
        photo = FSInputFile(qr_code_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=f"📱 <b>QR-код для получения подарка</b>\n\n"
                    f"Используйте этот QR-код для получения вашего подарка в пункте выдачи заказов.\n\n"
                    f"Группа: {group['name']}",
            parse_mode="HTML"
        )
        await callback.answer("✅ QR-код отправлен")

    except Exception as e:
        print(f"Ошибка при отправке QR-кода: {e}")
        await callback.answer("❌ Ошибка при отправке QR-кода", show_alert=True)
