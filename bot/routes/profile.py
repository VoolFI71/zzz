from aiogram import Router, F, types
from keyboards import keyboard
import aiohttp
import json
import os
import time
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
                            response_message = (
                                f"vless://{user['user_code']}@77.110.108.194:443?"
                                "security=reality&encryption=none&pbk=bMhOMGZho4aXhfoxyu7D9ZjVnM-02bR9dKBfIMMTVlc&"
                                "headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=google.com&sid=094e39c18a0e44#godnetvpn.\n"
                            )
                            await message.answer(response_message + "\n", reply_markup=keyboard.create_keyboard())
                    else:
                        await message.answer("У вас нет конфигов")
                else:
                    error_message = await response.json()
                    await message.answer(f"{error_message.get('detail', 'Неизвестная ошибка')}", reply_markup=keyboard.create_keyboard())
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка соединения: {str(e)}", reply_markup=keyboard.create_keyboard())
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}", reply_markup=keyboard.create_keyboard())