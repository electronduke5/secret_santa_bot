from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from keyboards import main_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        f"🎅 <b>Добро пожаловать в бота Тайный Санта!</b>\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу организовать игру в Тайного Санту для вашей компании.\n\n"
        f"<b>Что я умею:</b>\n"
        f"• Создавать группы для игры\n"
        f"• Приглашать участников по специальному коду\n"
        f"• Случайно распределять участников\n"
        f"• Хранить списки пожеланий к подаркам\n\n"
        f"Выберите действие из меню ниже:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        f"🎅 <b>Главное меню</b>\n\n"
        f"Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()
