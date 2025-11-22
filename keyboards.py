from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎅 Создать группу", callback_data="create_group")],
        [InlineKeyboardButton(text="👥 Мои группы", callback_data="my_groups")],
        [InlineKeyboardButton(text="📝 Присоединиться", callback_data="join_group")],
    ])
    return keyboard


def group_list_keyboard(groups: List[dict]) -> InlineKeyboardMarkup:
    """Клавиатура со списком групп пользователя"""
    buttons = []

    for group in groups:
        status = "✅" if group["is_distributed"] else "⏳"
        button_text = f"{status} {group['name']} ({group['participants_count']} чел.)"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"group_info_{group['invite_code']}"
        )])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def group_info_keyboard(invite_code: str, is_admin: bool, is_distributed: bool, user_id: int = None, has_qr_code: bool = False, recipient_has_qr: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с действиями для группы"""
    buttons = []

    # Общие кнопки для всех участников
    buttons.append([InlineKeyboardButton(
        text="📋 Список участников",
        callback_data=f"participants_{invite_code}"
    )])

    buttons.append([InlineKeyboardButton(
        text="🎁 Мой список пожеланий",
        callback_data=f"set_wishlist_{invite_code}"
    )])

    # Кнопки только для админа
    if is_admin:
        buttons.append([InlineKeyboardButton(
            text="🔗 Пригласительная ссылка",
            callback_data=f"invite_link_{invite_code}"
        )])

        if not is_distributed:
            buttons.append([InlineKeyboardButton(
                text="🎲 Начать распределение",
                callback_data=f"start_distribution_{invite_code}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text="🔄 Отменить распределение",
                callback_data=f"cancel_distribution_{invite_code}"
            )])

    # Кнопка для просмотра получателя (после распределения)
    if is_distributed:
        buttons.append([InlineKeyboardButton(
            text="🎁 Кому я дарю подарок?",
            callback_data=f"my_recipient_{invite_code}"
        )])

        # Кнопки для работы с QR-кодами (только после распределения)
        if user_id:
            # Кнопка загрузки/замены QR-кода для дарителя
            if has_qr_code:
                buttons.append([InlineKeyboardButton(
                    text="🔄 Заменить QR-код",
                    callback_data=f"upload_qr_{invite_code}"
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text="📤 Загрузить QR-код",
                    callback_data=f"upload_qr_{invite_code}"
                )])

            # Кнопка просмотра QR-кода для получателя
            if recipient_has_qr:
                buttons.append([InlineKeyboardButton(
                    text="📱 Посмотреть QR-код получения",
                    callback_data=f"view_qr_{invite_code}"
                )])

    buttons.append([InlineKeyboardButton(text="◀️ К моим группам", callback_data="my_groups")])

    # Кнопка удаления группы (только для админа)
    if is_admin:
        buttons.append([InlineKeyboardButton(
            text="🗑️ Удалить группу",
            callback_data=f"delete_group_{invite_code}"
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_button() -> InlineKeyboardMarkup:
    """Кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])


def confirm_distribution(invite_code: str) -> InlineKeyboardMarkup:
    """Подтверждение распределения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, начать", callback_data=f"confirm_dist_{invite_code}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"group_info_{invite_code}")]
    ])


def cancel_action(callback_data: str) -> InlineKeyboardMarkup:
    """Кнопка отмены действия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=callback_data)]
    ])


def confirm_delete_group(invite_code: str) -> InlineKeyboardMarkup:
    """Подтверждение удаления группы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить навсегда", callback_data=f"confirm_delete_{invite_code}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"group_info_{invite_code}")]
    ])
