from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import keyboard
import aiohttp
import json
import os
import time
import urllib.parse
router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")

@router.message(F.text == "Личный кабинет")
async def my_account(message: types.Message):
    user_id = message.from_user.id
    url = f"http://fastapi:8080/usercodes/{user_id}"
    headers = {"X-API-Key": AUTH_CODE}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data:
                        for i, user in enumerate(response_data, start=1):
                            remaining_seconds = user['time_end'] - int(time.time()) 
                            if remaining_seconds <= 0 :
                                await message.answer(f"Время действия конфига истекло \n")
                            else: 
                                exptime = remaining_seconds / 3600
                                await message.answer(f"Конфиг {i}. Оставшееся время действия: {exptime:.2f} часов \n")
                            
                            # Создаем VLESS конфиг
                            vless_config = (
                                f"vless://{user['user_code']}@77.110.108.194:443?"
                                "security=reality&encryption=none&pbk=bMhOMGZho4aXhfoxyu7D9ZjVnM-02bR9dKBfIMMTVlc&"
                                "headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=google.com&sid=094e39c18a0e44#godnetvpn"
                            )
                            
                            # Создаем URL для веб-страницы добавления конфига
                            import base64
                            encoded_config = base64.b64encode(vless_config.encode()).decode()
                            remaining_seconds = user['time_end'] - int(time.time())
                            web_url = f"http://127.0.0.1:8080/add-config?config={encoded_config}&expiry={remaining_seconds}"
                            
                            # Создаем inline клавиатуру с кнопкой для V2rayTun
                            inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📱 Добавить в V2rayTun", url=web_url)],
                                [InlineKeyboardButton(text="📋 Копировать конфиг", callback_data=f"copy_config_{i}")]
                            ])
                            
                            # Создаем красивое сообщение вместо огромного конфига
                            remaining_hours = remaining_seconds // 3600
                            remaining_days = remaining_hours // 24
                            
                            if remaining_days > 0:
                                time_text = f"{remaining_days} дн. {remaining_hours % 24} ч."
                            else:
                                time_text = f"{remaining_hours} ч."
                            
                            config_message = (
                                f"🔐 <b>Конфиг #{i}</b>\n"
                                f"⏰ Действует: <b>{time_text}</b>\n"
                                f"🌐 Сервер: <code>Финляндия 🇫🇮</code>\n\n"
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