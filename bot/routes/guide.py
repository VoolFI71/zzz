from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard

router = Router()

# Поддерживаем старый и новый варианты кнопки
@router.message(F.text.in_({"Инструкция⚙️", "🛠️ Инструкция"}))
async def guide_command(message: types.Message):
    await message.answer("📚 Выберите способ установки:", reply_markup=keyboard.create_settings_keyboard())

@router.message(F.text.in_({"Установка на Телефон", "📱 Установка на Телефон", "Установка на телефон", "📱 Установка на телефон"}))
async def tel_guide_command(message: types.Message):
    await message.answer(
        "📱 Установка на телефон (Android/iOS):\n\n"
        "1) Установите v2RayTun: [Android](https://play.google.com/store/apps/details?id=com.v2raytun.android), [iOS](https://apps.apple.com/ru/app/v2raytun/id6476628951).\n"
        "2) Получите подписку в Личном кабинете (кнопка ‘Добавить подписку в V2rayTun’).\n"
        "3) Нажмите открыть — приложение добавит подписку.\n\n"
        "Если что‑то не так и подписка не добавилась автоматически:\n"
        "• Нажмите 📋 Скопировать ссылку в боте.\n"
        "• Откройте V2rayTun → Нажать на + → Импорт из буфера.\n"
        "• Подключитесь.",
        reply_markup=keyboard.create_keyboard(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

@router.message(F.text.in_({"Установка на PC", "💻 Установка на PC", "Установка на ПК", "💻 Установка на ПК"}))
async def pc_guide_command(message: types.Message):
    await message.answer("💻 Установка на компьютер (Windows/macOS/Linux):\n\n"
    "- Windows: v2RayTun — [скачать](https://v2raytun.com)\n"
    "- Windows: v2RayN — [скачать](https://github.com/2dust/v2rayN/releases/download/7.13.2/v2rayN-windows-64.zip)\n"
    "- macOS: v2RayTun — [App Store](https://apps.apple.com/ru/app/v2raytun/id6476628951)\n"
    "- Альтернатива (Win/macOS/Linux): [AmneziaVPN](https://amnezia.app/ru/downloads)\n\n"
    "Скопируйте конфиг из Личного кабинета, импортируйте в приложение и подключайтесь.", 
    reply_markup=keyboard.create_keyboard(),
    parse_mode='Markdown',
    disable_web_page_preview=True
    )

@router.message(F.text.in_({"Поддержка", "🆘 Поддержка"}))
async def support_command(message: types.Message):
    await message.answer("@helpervpn71")

@router.message(F.text.in_({"Назад", "🔙 Назад"}))
async def back_command(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=keyboard.create_keyboard())