"""
Управление конфигами пользователя.
"""

import os
import time
import aiohttp
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import keyboard
from utils import should_throttle, acquire_action_lock, get_session
from database import db

router = Router()

AUTH_CODE = os.getenv("AUTH_CODE")

@router.message(F.text.in_({"Мои конфиги", "📂 Мои конфиги"}))
async def my_configs(message: types.Message):
    """Показывает активные конфигурации пользователя."""
    user_id = message.from_user.id
    throttled, retry_after = should_throttle(user_id, "my_configs", cooldown_seconds=3.0)
    if throttled:
        await message.answer(f"Слишком часто. Попробуйте через {int(retry_after)} сек.")
        return
    url = f"http://fastapi:8080/usercodes/{user_id}"
    headers = {"X-API-Key": AUTH_CODE}

    try:
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
                            # Пытаемся создать sub_key принудительно
                            try:
                                sub_key = await db.get_or_create_sub_key(str(user_id))
                            except Exception:
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
                    error_detail = error_message.get('detail', 'Неизвестная ошибка')
                    if "404" in str(error_detail) or "not found" in str(error_detail).lower():
                        await message.answer("🔍 Конфигурации не найдены. Возможно, у вас нет активных подписок.", reply_markup=keyboard.create_profile_keyboard())
                    elif "timeout" in str(error_detail).lower():
                        await message.answer("⏱️ Серверы временно недоступны. Попробуйте через 2-3 минуты.", reply_markup=keyboard.create_profile_keyboard())
                    else:
                        await message.answer("❌ Не удалось получить конфигурации. Обратитесь в поддержку.", reply_markup=keyboard.create_profile_keyboard())
    except aiohttp.ClientError as e:
        if "timeout" in str(e).lower():
            await message.answer("⏱️ Серверы временно недоступны. Попробуйте через 2-3 минуты.", reply_markup=keyboard.create_profile_keyboard())
        elif "connection" in str(e).lower():
            await message.answer("🌐 Проблемы с подключением. Проверьте интернет и попробуйте позже.", reply_markup=keyboard.create_profile_keyboard())
        else:
            await message.answer("❌ Ошибка сети. Попробуйте позже или обратитесь в поддержку.", reply_markup=keyboard.create_profile_keyboard())
    except Exception as e:
        await message.answer("❌ Произошла неожиданная ошибка. Обратитесь в поддержку.", reply_markup=keyboard.create_profile_keyboard())
