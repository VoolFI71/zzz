from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import keyboard
import aiohttp
import os
import time
import urllib.parse
router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://77.110.108.194:8080")

countryies_settings = {
    "fi": {
        "host": "77.110.108.194",
        "pbk": "pX2kfQomg0q6W38ndY1cS-G-ohj2jkFBmQwsmOh2nTQ",
        "sni": "google.com",
        "sid": "74d3d8efef7f8e27",
        "country": "Финляндия 🇫🇮"
    }
}

@router.message(F.text == "Личный кабинет")
async def my_account(message: types.Message):
    user_id = message.from_user.id
    url = f"http://fastapi:8080/usercodes/{user_id}"
    headers = {"X-API-Key": AUTH_CODE}

    try:
        from utils import get_session
        session = await get_session()
        async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data:
                        for i, user in enumerate(response_data, start=1):
                            remaining_seconds = user['time_end'] - int(time.time()) 
                            
                            # Пропускаем истекшие конфиги
                            if remaining_seconds <= 0:
                                continue
    
                            # Создаем VLESS конфиг
                            settings = countryies_settings[user['server']]
                            vless_config = (
                                f"vless://{user['user_code']}@{settings['host']}:443?"
                                f"security=reality&encryption=none&pbk={settings['pbk']}&"
                                f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
                                f"sni={settings['sni']}&sid={settings['sid']}#glsvpn"
                            )
                            
                            # Создаем URL для веб-страницы добавления конфига и прямого редиректа
                            import base64
                            encoded_config = base64.b64encode(vless_config.encode()).decode()
                            remaining_seconds = user['time_end'] - int(time.time())
                            web_url = f"{PUBLIC_BASE_URL}/add-config?config={encoded_config}&expiry={remaining_seconds}"
                            # redirect_url = f"{PUBLIC_BASE_URL}/redirect?config={urllib.parse.quote(vless_config, safe='')}"
                            
                            # Создаем inline клавиатуру с двумя одинаковыми кнопками (вторая ведёт на /redirect)
                            inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📱 Добавить в V2rayTun", url=web_url)],
                                [InlineKeyboardButton(text="📋 Копировать конфиг", callback_data=f"copy_config_{i}")]
                            ])
                            
                            # Создаем красивое сообщение вместо огромного конфига
                            remaining_hours = remaining_seconds // 3600
                            remaining_days = remaining_hours // 24
                            hours_left = remaining_hours % 24
                            
                            if remaining_days > 0:
                                if hours_left > 0:
                                    time_text = f"{remaining_days} дн. {hours_left} ч."
                                else:
                                    time_text = f"{remaining_days} дн."
                            else:
                                time_text = f"{remaining_hours} ч."
                            
                            config_message = (
                                f"🔐 <b>Конфиг #{i}</b>\n"
                                f"⏰ Действует: <b>{time_text}</b>\n"
                                f"🌐 Сервер: <code>{countryies_settings[user['server']]['country']}</code>\n\n"
                                f"💡 <i>Нажмите кнопку ниже для добавления в приложение</i>"
                            )
                            
                            await message.answer(
                                config_message,
                                parse_mode="HTML",
                                reply_markup=inline_kb
                            )
                        
                        # Показываем основную клавиатуру после всех конфигов
                        await message.answer("Выберите действие:", reply_markup=keyboard.create_keyboard())
                    else:
                        await message.answer("У вас нет конфигов", reply_markup=keyboard.create_keyboard())
                else:
                    error_message = await response.json()
                    await message.answer(f"{error_message.get('detail', 'Неизвестная ошибка')}", reply_markup=keyboard.create_keyboard())
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка соединения: {str(e)}", reply_markup=keyboard.create_keyboard())
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}", reply_markup=keyboard.create_keyboard())

@router.callback_query(F.data.startswith("copy_config_"))
async def copy_config_callback(callback: types.CallbackQuery):
    """Обработчик для кнопки копирования конфига"""
    await callback.answer("Конфиг скопирован! Вставьте его в V2rayTun вручную.", show_alert=True)