from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import keyboard
from utils import should_throttle, acquire_action_lock
import aiohttp
import os
import time
from database import db
router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")

# Читает первое непустое значение из списка env-ключей
def _env_any(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


# Note: COUNTRY_SETTINGS and PUBLIC_BASE_URL are maintained in FastAPI app; not needed in bot layer


# Поддерживаем старый и новый варианты кнопки
@router.message(F.text.in_({"Личный кабинет", "👤 Личный кабинет"}))
async def my_account(message: types.Message):
    # Переходим в подменю профиля
    await message.answer("Личный кабинет:", reply_markup=keyboard.create_profile_keyboard())


@router.message(F.text.in_({"Пробная 3 дня", "🎁 Пробная 3 дня", "Пробные 3 дня", "🎁 Пробные 3 дня"}))
async def free_trial(message: types.Message):
    user_id = message.from_user.id
    # Throttle repeated clicks
    throttled, retry_after = should_throttle(user_id, "free_trial", cooldown_seconds=5.0)
    if throttled:
        await message.answer(f"Слишком часто. Попробуйте через {int(retry_after)+1} сек.")
        return
    try:
        await db.ensure_user_row(str(user_id))
        if await db.has_used_trial_3d(str(user_id)):
            await message.answer("Вы уже активировали пробную подписку ранее.")
            return
    except Exception:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    # Проверяем наличие свободных конфигов (не блокирующе)
    from utils import get_session
    # Пытаемся выдать на первом доступном сервере из списка (по умолчанию fi, nl)
    from utils import pick_first_available_server
    server_order_env = os.getenv("SERVER_ORDER", "fi")
    preferred = [s.strip().lower() for s in server_order_env.split(',') if s.strip()]
    target_server = await pick_first_available_server(preferred)
    if not target_server:
        await message.answer("Свободных конфигов нет. Попробуйте позже.")
        return

    # Выдаём бесплатные 3 дня на сервере FI
    data = {"time": 3, "id": str(user_id), "server": target_server}
    AUTH_CODE = os.getenv("AUTH_CODE")
    urlupdate = "http://fastapi:8080/giveconfig"
    try:
        session = await get_session()
        async with acquire_action_lock(user_id, "free_trial"):
            async with session.post(urlupdate, json=data, headers={"X-API-Key": AUTH_CODE}) as resp:
                if resp.status == 200:
                    await user_db.set_trial_3d_used(str(user_id))
                    base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
                    try:
                        sub_url = f"http://fastapi:8080/sub/{user_id}"
                        async with session.get(sub_url, headers={"X-API-Key": AUTH_CODE}) as sub_resp:
                            if sub_resp.status == 200:
                                sub_data = await sub_resp.json()
                                sub_key = sub_data.get("sub_key")
                                if sub_key:
                                    web_url = f"{base}/subscription/{sub_key}"
                                else:
                                    web_url = f"{base}/subscription"
                            else:
                                web_url = f"{base}/subscription"
                    except Exception:
                        # Fallback на старую ссылку, если что-то пошло не так
                        web_url = f"{base}/subscription"
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📲 Добавить подписку в V2rayTun", url=web_url)],
                        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_sub")],
                    ])
                    await message.answer("Пробная подписка на 3 дня активирована!", reply_markup=kb)
                    await message.answer("Подписка может быть не добавлена при нажатии на кнопку на сайте, в этом случае необходимо скопировать ссылку на подписку и вставить в V2rayTun вручную.")

                    try:
                        admin_id = 746560409
                        at_username = (f"@{message.from_user.username}" if getattr(message.from_user, "username", None) else "—")
                        await message.bot.send_message(admin_id, f"Активирована пробная подписка: user_id={user_id}, user={at_username}, сервер=fi, срок=3 дн.")
                    except Exception:
                        pass
                elif resp.status == 409:
                    await message.answer("Свободных конфигов нет. Попробуйте позже.")
                else:
                    await message.answer(f"Ошибка сервера ({resp.status}). Попробуйте позже.")
    except aiohttp.ClientError:
        await message.answer("Ошибка сети. Попробуйте позже.")


@router.callback_query(F.data.startswith("copy_config_"))
async def copy_config_callback(callback: types.CallbackQuery):
    """Теперь отдаём ссылку на подписку, которая подтянет все конфиги автоматически."""
    try:
        # idx из callback нам больше не нужен, но парсим безопасно для обратной совместимости
        _ = int(callback.data.split("_")[-1]) if callback.data.rsplit("_", 1)[-1].isdigit() else None
    except Exception:
        pass

    user_id = callback.from_user.id
    headers = {"X-API-Key": AUTH_CODE}

    try:
        from utils import get_session
        session = await get_session()
        async with acquire_action_lock(user_id, "copy_config"):
            # Получаем постоянный sub_key из внутреннего API
            sub_url_api = f"http://fastapi:8080/sub/{user_id}"
            async with session.get(sub_url_api, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    await callback.answer("Ошибка. Попробуйте позже", show_alert=True)
                    return
                data = await resp.json()
                sub_key = data.get("sub_key")
                if not sub_key:
                    await callback.answer("Не удалось получить ссылку", show_alert=True)
                    return
            # Формируем публичную ссылку подписки
            base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
            web_url = f"{base}/subscription/{sub_key}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📲 Добавить подписку в V2rayTun", url=web_url)],
                [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_sub")],
            ])
            await callback.message.answer("Ваша подписка:", reply_markup=kb, disable_web_page_preview=True)
            await callback.answer()
    except aiohttp.ClientError:
        await callback.answer("Ошибка сети", show_alert=True)
    except Exception:
        await callback.answer("Ошибка", show_alert=True)


@router.message(F.text.in_({"Мои конфиги", "📂 Мои конфиги"}))
async def my_configs(message: types.Message):
    user_id = message.from_user.id
    throttled, retry_after = should_throttle(user_id, "my_configs", cooldown_seconds=3.0)
    if throttled:
        await message.answer(f"Слишком часто. Попробуйте через {int(retry_after)} сек.")
        return
    url = f"http://fastapi:8080/usercodes/{user_id}"
    headers = {"X-API-Key": AUTH_CODE}

    try:
        from utils import get_session
        session = await get_session()
        async with acquire_action_lock(user_id, "my_configs"):
            async with session.get(url, timeout=10, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if response_data:
                        def _parse_time_end(raw: object) -> int:
                            try:
                                val = int(raw)
                            except Exception:
                                return 0
                            # Heuristic: if value looks like milliseconds, convert to seconds
                            if val > 10**11:
                                val = val // 1000
                            return val
                        skew_tolerance = 5  # seconds
                        # Сводка по странам
                        now_ts = int(time.time())
                    
                        active_configs = []
                        # Map server code -> nice title and flag
                        server_titles = {
                            'fi': 'Финляндия',
                            'nl': 'Нидерланды',
                            'ge': 'Германия',
                        }
                        server_flags = {
                            'fi': '🇫🇮',
                            'nl': '🇳🇱',
                            'ge': '🇩🇪',
                        }

                        def _fmt_duration(seconds: int) -> str:
                            seconds = max(0, int(seconds))
                            days = seconds // 86400
                            hours = (seconds % 86400) // 3600
                            minutes = (seconds % 3600) // 60
                            if days > 0:
                                return f"{days} дн {hours} ч"
                            if hours > 0:
                                return f"{hours} ч {minutes} мин"
                            return f"{minutes} мин"

                        for user in response_data:
                            time_end = _parse_time_end(user.get('time_end', 0))
                            if time_end >= (now_ts - skew_tolerance):
                                srv = str(user.get('server', ''))
                                title = server_titles.get(srv, srv.upper())
                                flag = server_flags.get(srv, '')
                                remaining_secs = time_end - now_ts
                                active_configs.append(f"- {flag} {title}: {_fmt_duration(remaining_secs)}")

                        if not active_configs:
                            await message.answer("У вас нет активных конфигураций", reply_markup=keyboard.create_profile_keyboard())
                            return

                        text = "Ваши активные конфигурации:\n" + "\n".join(active_configs)

                        # Постоянная ссылка подписки по sub_key
                        sub_url = f"http://fastapi:8080/sub/{user_id}"
                        try:
                            async with session.get(sub_url, timeout=10, headers=headers) as resp:
                                if resp.status != 200:
                                    await message.answer("Ошибка. Попробуйте позже.", reply_markup=keyboard.create_profile_keyboard())
                                    return
                                data = await resp.json()
                        except aiohttp.ClientError as e:
                            await message.answer(f"Ошибка соединения: {str(e)}", reply_markup=keyboard.create_profile_keyboard())
                            return
                        except Exception:
                            await message.answer("Ошибка. Попробуйте позже.", reply_markup=keyboard.create_profile_keyboard())
                            return

                        sub_key = data.get("sub_key")
                        if not sub_key:
                            await message.answer("Не удалось получить sub_key.", reply_markup=keyboard.create_profile_keyboard())
                            return

                        web_url = f"https://swaga.space/subscription/{sub_key}"
                        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📲 Добавить подписку в V2rayTun", url=web_url)],
                            [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_sub")],
                        ])
                        await message.answer(text, reply_markup=inline_kb, disable_web_page_preview=True)
                        await message.answer("Подписка может быть не добавлена при нажатии на кнопку на сайте, в этом случае необходимо скопировать ссылку на подписку и вставить в V2rayTun вручную.")
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

        
@router.callback_query(F.data == "copy_sub")
async def copy_subscription_callback(callback: types.CallbackQuery):
    """Отправляет пользователю его ссылку на подписку для копирования."""
    user_id = callback.from_user.id
    headers = {"X-API-Key": AUTH_CODE}
    try:
        from utils import get_session
        session = await get_session()
        sub_url_api = f"http://fastapi:8080/sub/{user_id}"
        async with acquire_action_lock(user_id, "copy_sub"):
            async with session.get(sub_url_api, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    await callback.answer("Ошибка", show_alert=True)
                    return
                data = await resp.json()
                sub_key = data.get("sub_key")
                if not sub_key:
                    await callback.answer("Нет ссылки", show_alert=True)
                    return
        base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
        web_url = f"{base}/subscription/{sub_key}"
        # Редактируем текущее сообщение: показываем только ссылку без кнопок
        try:
            await callback.message.edit_text(web_url, disable_web_page_preview=True)
        except Exception:
            try:
                # Если редактирование недоступно (старое сообщение) — отправим новым сообщением
                await callback.message.answer(web_url, disable_web_page_preview=True)
            except Exception:
                pass
        # Сообщаем пользователю
        try:
            await callback.answer("Скопируйте ссылку", show_alert=False)
        except Exception:
            pass
    except Exception:
        try:
            await callback.answer("Ошибка", show_alert=True)
        except Exception:
            pass

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


@router.message(F.text.in_({"Активировать дни", "✨ Активировать дни"}))
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