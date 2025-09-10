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
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://swaga.space")

# Читает первое непустое значение из списка env-ключей
def _env_any(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


COUNTRY_SETTINGS: dict[str, dict[str, str]] = {
    "nl": {
        "urlcreate": _env_any("URLCREATE_NL", "urlcreate_nl", default=""),
        "urlupdate": _env_any("URLUPDATE_NL", "urlupdate_nl", default=""),
        "urldelete": _env_any("URLDELETE_NL", "urldelete_nl", default=""),
        # Параметры для генерации VLESS
        "host": _env_any("HOST_NL", "host_nl", default=""),
        "pbk": _env_any("PBK_NL", "pbk_nl", default=""),
        "sni": "google.com",
        "sid": _env_any("SID_NL", "sid_nl", default=""),
    },
    "fi": {
        "urlcreate": _env_any("URLCREATE_FI", "urlcreate_fi", default=""),
        "urlupdate": _env_any("URLUPDATE_FI", "urlupdate_fi", default=""),
        "urldelete": _env_any("URLDELETE_FI", "urldelete_fi", default=""),
        # Параметры для генерации VLESS
        "host": _env_any("HOST_FI", "host_fi", default="77.110.108.194"),
        "pbk": _env_any("PBK_FI", "pbk_fi", default=""),
        "sni": "google.com",
        "sid": _env_any("SID_FI", "sid_fi", default=""),
    },
}


@router.message(F.text == "Личный кабинет")
async def my_account(message: types.Message):
    # Переходим в подменю профиля
    await message.answer("Личный кабинет:", reply_markup=keyboard.create_profile_keyboard())

@router.message(F.text == "🎁 Пробная 7 дней")
async def free_trial(message: types.Message):
    user_id = message.from_user.id
    from database import db as user_db
    try:
        await user_db.ensure_user_row(str(user_id))
        if await user_db.has_used_trial_3d(str(user_id)):
            await message.answer("Вы уже активировали пробную подписку ранее.")
            return
    except Exception:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    # Проверяем наличие свободных конфигов (не блокирующе)
    from utils import check_available_configs, get_session
    available = await check_available_configs("fi")
    if not available:
        await message.answer("Свободных конфигов нет. Попробуйте позже.")
        return

    # Выдаём бесплатные 7 дней на сервере FI
    data = {"time": 7, "id": str(user_id), "server": "fi"}
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"
    try:
        session = await get_session()
        async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
            if resp.status == 200:
                await user_db.set_trial_3d_used(str(user_id))
                base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
                web_url = f"{base}/add-config?tg_id={user_id}"
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📲 Добавить в V2rayTun", url=web_url)]])
                await message.answer("Пробная подписка на 7 дней активирована!", reply_markup=kb)
            elif resp.status == 409:
                await message.answer("Свободных конфигов нет. Попробуйте позже.")
            else:
                await message.answer(f"Ошибка сервера ({resp.status}). Попробуйте позже.")
    except aiohttp.ClientError:
        await message.answer("Ошибка сети. Попробуйте позже.")

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
            settings = COUNTRY_SETTINGS[user['server']]
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
                        settings = COUNTRY_SETTINGS[user['server']]
                        vless_config = (
                            f"vless://{user['user_code']}@{settings['host']}:443?"
                            f"security=reality&encryption=none&pbk={settings['pbk']}&"
                            f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
                            f"sni={settings['sni']}&sid={settings['sid']}#glsvpn"
                        )
                        base = PUBLIC_BASE_URL.rstrip('/')
                        web_url = f"{base}/add-config?tg_id={user_id}"
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
                             f"🌐 Сервер: <code>{COUNTRY_SETTINGS[user['server']].get('country', user['server'])}</code>\n\n"
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