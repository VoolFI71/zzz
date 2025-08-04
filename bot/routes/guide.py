from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import keyboard

router = Router()

@router.message(F.text == "Инструкция⚙️")
async def guide_command(message: types.Message):
    await message.answer("Выберите способ установки:", reply_markup=keyboard.create_settings_keyboard())

@router.message(F.text == "Установка на Телефон")
async def tel_guide_command(message: types.Message):
    await message.answer(
        "Установка подключения на [Android](https://play.google.com/store/apps/details?id=com.v2raytun.android) и [iOS](https://apps.apple.com/ru/app/v2raytun/id6476628951) идентична. Чтобы подключиться к серверу необходимо установить приложение v2RayTun. Скопировать конфиг подключения из личного кабинета в боте. Вставить конфиг из буфера обмена в установленном приложении и подключиться.",
        reply_markup=keyboard.create_keyboard(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

@router.message(F.text == "Установка на PC")
async def pc_guide_command(message: types.Message):
    await message.answer("Чтобы подключиться к серверу необходимо установить приложение v2RayN [IOS](https://apps.apple.com/ru/app/v2raytun/id6476628951), [Windows, Linux](https://github.com/2dust/v2rayN/releases/download/7.13.2/v2rayN-windows-64.zip). Простая установка для всех устройств [Amneziavpn](https://amnezia.app/ru/downloads). Скопировать конфиг подключения из личного кабинета в боте. Вставить конфиг из буфера обмена в установленном приложении и подключиться", 
    reply_markup=keyboard.create_keyboard(),
    parse_mode='Markdown',
    disable_web_page_preview=True
    )

@router.message(F.text == "Назад")
async def back_command(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=keyboard.create_keyboard())