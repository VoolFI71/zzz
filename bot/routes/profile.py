from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import keyboard
import aiohttp
import os
import time
import urllib.parse
from database import db
router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://77.110.108.194:8080")

countries_settings = {
    "fi": {
        "host": "77.110.108.194",
        "pbk": "MCYfahzGBFZW2V3Pf9XivR36CrnAUQiVfehSXgFwwVE",
        "sni": "google.com",
        "sid": "fb77c9c3d3ef",
        "country": "Финляндия 🇫🇮"
    }
}

@router.message(F.text == "Личный кабинет")
async def my_account(message: types.Message):
    # Переходим в подменю профиля
    await message.answer("Личный кабинет:", reply_markup=keyboard.create_profile_keyboard())

@router.callback_query(F.data.startswith("copy_config_"))
async def copy_config_callback(callback: types.CallbackQuery):
    """Показывает конфиг в виде текста для копирования + кнопку удаления сообщения."""
    try:
        idx_str = callback.data.split("_")[-1]
        idx = int(idx_str)
    except Exception:
        await callback.answer("Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    url = f"http://fastapi:8080/usercodes/{user_id}"
    headers = {"X-API-Key": AUTH_CODE}

    try:
        from utils import get_session
        session = await get_session()
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                await callback.answer("Конфиг не найден", show_alert=True)
                return
            response_data = await response.json()
            if not response_data or idx < 1 or idx > len(response_data):
                await callback.answer("Конфиг не найден", show_alert=True)
                return
            user = response_data[idx - 1]
            remaining_seconds = user['time_end'] - int(time.time())
            if remaining_seconds <= 0:
                await callback.answer("Срок действия истёк", show_alert=True)
                return
            settings = countries_settings[user['server']]
            vless_config = (
                f"vless://{user['user_code']}@{settings['host']}:443?"
                f"security=reality&encryption=none&pbk={settings['pbk']}&"
                f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
                f"sni={settings['sni']}&sid={settings['sid']}#glsvpn"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить это сообщение", callback_data="delmsg")]])
            await callback.message.answer(f"<code>{vless_config}</code>", parse_mode="HTML", reply_markup=kb)
            await callback.answer()
    except aiohttp.ClientError:
        await callback.answer("Ошибка сети", show_alert=True)
    except Exception:
        await callback.answer("Ошибка", show_alert=True)


@router.message(F.text == "Мои конфиги")
async def my_configs(message: types.Message):
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
                        if remaining_seconds <= 0:
                            continue
                        settings = countries_settings[user['server']]
                        vless_config = (
                            f"vless://{user['user_code']}@{settings['host']}:443?"
                            f"security=reality&encryption=none&pbk={settings['pbk']}&"
                            f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
                            f"sni={settings['sni']}&sid={settings['sid']}#glsvpn"
                        )
                        import base64
                        encoded_config = base64.b64encode(vless_config.encode()).decode()
                        web_url = f"swaga.space/add-config?config={encoded_config}&expiry={remaining_seconds}"
                        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📱 Добавить в V2rayTun", url=web_url)],
                            [InlineKeyboardButton(text="📋 Копировать конфиг", callback_data=f"copy_config_{i}")]
                        ])
                        remaining_hours = remaining_seconds // 3600
                        remaining_days = remaining_hours // 24
                        hours_left = remaining_hours % 24
                        if remaining_days > 0:
                            time_text = f"{remaining_days} дн. {hours_left} ч." if hours_left > 0 else f"{remaining_days} дн."
                        else:
                            time_text = f"{remaining_hours} ч."
                        config_message = (
                            f"🔐 <b>Конфиг #{i}</b>\n"
                            f"⏰ Действует: <b>{time_text}</b>\n"
                            f"🌐 Сервер: <code>{countries_settings[user['server']]['country']}</code>\n\n"
                            f"💡 <i>Нажмите кнопку ниже для добавления в приложение</i>"
                        )
                        await message.answer(config_message, parse_mode="HTML", reply_markup=inline_kb)
                    await message.answer("Выберите действие:", reply_markup=keyboard.create_profile_keyboard())
                else:
                    await message.answer("У вас нет конфигов", reply_markup=keyboard.create_profile_keyboard())
            else:
                error_message = await response.json()
                await message.answer(f"{error_message.get('detail', 'Неизвестная ошибка')}", reply_markup=keyboard.create_profile_keyboard())
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка соединения: {str(e)}", reply_markup=keyboard.create_profile_keyboard())
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}", reply_markup=keyboard.create_profile_keyboard())


@router.callback_query(F.data == "delmsg")
async def delete_message_callback(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(F.text == "Активировать дни")
async def show_balance_activation(message: types.Message):
    tg_id = str(message.from_user.id)
    try:
        days = await db.get_balance_days(tg_id)
    except Exception:
        days = 0
    if days <= 0:
        await message.answer("На вашем балансе нет дней для активации.", reply_markup=keyboard.create_profile_keyboard())
        return
    await message.answer(
        f"На балансе: {days} дн. Нажмите кнопку ниже, чтобы активировать их как подписку.",
        reply_markup=keyboard.create_activate_balance_inline(days)
    )