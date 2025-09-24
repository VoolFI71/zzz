from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard

router = Router()

# Поддерживаем старый и новый варианты кнопки
@router.message(F.text.in_({"Инструкция⚙️", "🛠️ Инструкция"}))
async def guide_command(message: types.Message):
    await message.answer("📚 Выберите способ установки:", reply_markup=keyboard.create_settings_keyboard())

@router.message(F.text.in_({"Установка на Телефон", "📱 Установка на Телефон"}))
async def tel_guide_command(message: types.Message):
    await message.answer(
        "📱 Установка на телефон (Android/iOS):\n\n"
        "1) Установите v2RayTun: [Android](https://play.google.com/store/apps/details?id=com.v2raytun.android), [iOS](https://apps.apple.com/ru/app/v2raytun/id6476628951).\n"
        "2) Получите конфиг в Личном кабинете.\n"
        "3) Добавьте конфиг в приложение и подключитесь.",
        reply_markup=keyboard.create_keyboard(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

@router.message(F.text.in_({"Установка на PC", "💻 Установка на PC"}))
async def pc_guide_command(message: types.Message):
    await message.answer("💻 Установка на компьютер:\n\n"
    "- v2RayN: [Windows/Linux](https://github.com/2dust/v2rayN/releases/download/7.13.2/v2rayN-windows-64.zip)\n"
    "- Альтернатива: [AmneziaVPN](https://amnezia.app/ru/downloads)\n\n"
    "Скопируйте конфиг из Личного кабинета, вставьте в приложение и подключайтесь.", 
    reply_markup=keyboard.create_keyboard(),
    parse_mode='Markdown',
    disable_web_page_preview=True
    )

@router.message(F.text.in_({"Назад", "🔙 Назад"}))
async def back_command(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=keyboard.create_keyboard())