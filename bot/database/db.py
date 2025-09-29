from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiohttp
import aiosqlite
import random
import asyncio
import os
import time

async def init_db():
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        # Если таблица ещё не создана – создаём без поля email
        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        exists = await cursor.fetchone()
        if not exists:
            # Создаём таблицу сразу со всеми необходимыми столбцами
            await cursor.execute('''
                CREATE TABLE users (
                    tg_id TEXT UNIQUE,
                    referral_code TEXT UNIQUE,
                    referred_by TEXT,
                    referral_count INTEGER DEFAULT 0,
                    trial_3d_used INTEGER DEFAULT 0,
                    balance INTEGER DEFAULT 0,
                    paid_count INTEGER DEFAULT 0,
                    last_payment_at INTEGER DEFAULT 0
                )
            ''')
            await conn.commit()
        else:
            # Миграции для уже существующей таблицы (баланс / оплаты)
            await cursor.execute("PRAGMA table_info(users)")
            columns = await cursor.fetchall()
            col_names = {row[1] for row in columns}
            if "balance" not in col_names:
                await cursor.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
            if "paid_count" not in col_names:
                await cursor.execute("ALTER TABLE users ADD COLUMN paid_count INTEGER DEFAULT 0")
            if "last_payment_at" not in col_names:
                await cursor.execute("ALTER TABLE users ADD COLUMN last_payment_at INTEGER DEFAULT 0")
            await conn.commit()

        # Таблица агрегатов платежей (одна строка)
        await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments_agg'")
        agg_exists = await cursor.fetchone()
        if not agg_exists:
            await cursor.execute('''
                CREATE TABLE payments_agg (
                    id INTEGER PRIMARY KEY,
                    total_rub INTEGER DEFAULT 0,
                    total_stars INTEGER DEFAULT 0,
                    count_rub INTEGER DEFAULT 0,
                    count_stars INTEGER DEFAULT 0
                )
            ''')
            # Вставляем дефолтную строку
            await cursor.execute("INSERT INTO payments_agg (id, total_rub, total_stars, count_rub, count_stars) VALUES (1, 0, 0, 0, 0)")
            await conn.commit()

user_locks = {}

import aiosqlite

DB_PATH = "users.db"

async def get_referrer_id(user_tg_id: str):
    """
    Возвращает tg_id пользователя, который пригласил пользователя user_tg_id,
    или None если запись не найдена или referred_by пустой.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT referred_by FROM users WHERE tg_id = ?", (user_tg_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            ref = row["referred_by"]
            return ref if ref not in (None, "") else None


async def get_referral_code(tg_id):
    if tg_id not in user_locks:
        user_locks[tg_id] = asyncio.Lock()

    async with user_locks[tg_id]:  # Используем блокировку для синхронизации
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                # Шаг 1: Проверяем, есть ли у пользователя референс-код
                await cursor.execute("SELECT referral_code FROM users WHERE tg_id = ?", (tg_id,))
                result = await cursor.fetchone()

                # Если у пользователя уже есть референс-код, возвращаем его
                if result and result[0]:
                    return result[0]

                # Шаг 2: Если у пользователя нет референс-кода, проверяем наличие его записи
                await cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
                user_exists = await cursor.fetchone()

                # Если пользователя нет в базе данных, добавляем его
                if not user_exists:
                    await cursor.execute("INSERT INTO users (tg_id) VALUES (?)", (tg_id,))

                # Шаг 3: Генерируем новый уникальный референс-код
                while True:
                    referral_code = str(random.randint(10_000_000_000, 20_000_000_000))
                    await cursor.execute("SELECT COUNT(*) FROM users WHERE referral_code = ?", (referral_code,))
                    count = await cursor.fetchone()
                    if count[0] == 0:  # Уникальный код
                        break

                # Шаг 4: Устанавливаем новый референс-код для пользователя
                await cursor.execute(
                    "UPDATE users SET referral_code = ? WHERE tg_id = ?",
                    (referral_code, tg_id)
                )
                await conn.commit()
                return referral_code

async def is_first_time_user(user_id):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            # Проверяем, существует ли запись с таким tg_id
            await cursor.execute("SELECT tg_id FROM users WHERE tg_id = ?", (str(user_id),))
            exists_result = await cursor.fetchone()

            # Если пользователя нет в базе данных, считаем первым активатором
            if exists_result is None:
                return True

            # Если пользователь есть, проверяем, указан ли у него referred_by
            await cursor.execute("SELECT referred_by FROM users WHERE tg_id = ?", (str(user_id),))
            referred_by_result = await cursor.fetchone()

            # Возвращаем true, если поля referred_by нет или оно пустое
            return referred_by_result is None or referred_by_result[0] is None

async def get_referral_count(tg_id: str) -> int | None:
    """Возвращает количество приглашённых пользователем или None, если записи нет."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT referral_count FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            return row[0] if row else None

async def add_referral_by(user_id, referral_code, max_invites: int = 7) -> dict:
    """Добавляет связь реферала и увеличивает счётчик у пригласившего.

    Логика:
    - Счётчик приглашений растёт без потолка (может быть > max_invites), чтобы отображать, например, 10/7.
    - Бонус +2 дня выдаётся только если new_count <= max_invites.
    - Доп. бонус +15 дней выдаётся однократно на достижении new_count == max_invites.

    Возвращает словарь:
    - award_2d: bool — начислять ли +2 дня за это приглашение
    - award_15d: bool — начислять ли +15 дней (достигнут порог 7)
    - new_count: int — новое значение счётчика приглашений
    """
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            # 1. Создаём запись пользователя (если её нет) и выставляем referred_by
            await cursor.execute("SELECT tg_id FROM users WHERE tg_id = ?", (str(user_id),))
            if await cursor.fetchone() is None:
                await cursor.execute("INSERT INTO users (tg_id) VALUES (?)", (str(user_id),))

            await cursor.execute(
                "UPDATE users SET referred_by = ? WHERE tg_id = ?",
                (str(referral_code), str(user_id))
            )

            # 2. Проверяем текущий счётчик у пригласившего
            await cursor.execute(
                "SELECT referral_count FROM users WHERE referral_code = ?",
                (str(referral_code),)
            )
            row = await cursor.fetchone()
            current_count = row[0] if row and row[0] is not None else 0

            # 3. Всегда увеличиваем счётчик (для корректного отображения прогресса > 7)
            new_count = (current_count or 0) + 1
            await cursor.execute(
                "UPDATE users SET referral_count = ? WHERE referral_code = ?",
                (new_count, str(referral_code))
            )
            await conn.commit()

            award_2d = new_count <= max_invites
            award_15d = new_count == max_invites
            return {"award_2d": award_2d, "award_15d": award_15d, "new_count": new_count}

async def get_tg_id_by_referral_code(referral_code):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.execute("SELECT tg_id FROM users WHERE referral_code = ?", (referral_code,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


# -----------------------------
# Тестовая подписка 3 дня
# -----------------------------

async def ensure_user_row(tg_id: str) -> None:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT tg_id FROM users WHERE tg_id = ?", (str(tg_id),))
            exists = await cursor.fetchone()
            if exists is None:
                await cursor.execute("INSERT INTO users (tg_id) VALUES (?)", (str(tg_id),))
                await conn.commit()


async def has_used_trial_3d(tg_id: str) -> bool:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT trial_3d_used FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            return bool(row[0]) if row and row[0] is not None else False


async def set_trial_3d_used(tg_id: str) -> None:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("UPDATE users SET trial_3d_used = 1 WHERE tg_id = ?", (str(tg_id),))
            if cursor.rowcount == 0:
                # На случай отсутствия строки создадим её и повторим
                await cursor.execute("INSERT INTO users (tg_id, trial_3d_used) VALUES (?, 1)", (str(tg_id),))
            await conn.commit()


# -------------------------------------------------
# Оплаты: отметка и проверка
# -------------------------------------------------

async def mark_payment(tg_id: str, days: int) -> None:
    """Отмечает успешную оплату пользователем.

    - Увеличивает счётчик оплат paid_count
    - Обновляет last_payment_at текущим timestamp
    - По необходимости может пополнять баланс (но баланс уже списывается при выдаче конфига)
    """
    now_ts = int(time.time())
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT paid_count FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            current = int(row[0]) if row and row[0] is not None else 0
            await cursor.execute(
                "UPDATE users SET paid_count = ?, last_payment_at = ? WHERE tg_id = ?",
                (current + 1, now_ts, str(tg_id))
            )
            if cursor.rowcount == 0:
                await cursor.execute(
                    "INSERT INTO users (tg_id, paid_count, last_payment_at) VALUES (?, ?, ?)",
                    (str(tg_id), 1, now_ts)
                )
            await conn.commit()


async def has_any_payment(tg_id: str) -> bool:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT paid_count FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            return bool(row and row[0] and int(row[0]) > 0)


# -------------------------------------------------
# Агрегаты платежей (рубли / звёзды)
# -------------------------------------------------

async def add_rub_payment(amount_rub: int) -> None:
    amount_rub = int(amount_rub)
    if amount_rub <= 0:
        return
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE payments_agg SET total_rub = total_rub + ?, count_rub = count_rub + 1 WHERE id = 1",
                (amount_rub,)
            )
            if cursor.rowcount == 0:
                await cursor.execute(
                    "INSERT INTO payments_agg (id, total_rub, count_rub) VALUES (1, ?, 1)",
                    (amount_rub,)
                )
            await conn.commit()


async def add_star_payment(amount_stars: int) -> None:
    amount_stars = int(amount_stars)
    if amount_stars <= 0:
        return
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE payments_agg SET total_stars = total_stars + ?, count_stars = count_stars + 1 WHERE id = 1",
                (amount_stars,)
            )
            if cursor.rowcount == 0:
                await cursor.execute(
                    "INSERT INTO payments_agg (id, total_stars, count_stars) VALUES (1, ?, 1)",
                    (amount_stars,)
                )
            await conn.commit()


async def get_payments_aggregates() -> dict:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT total_rub, total_stars, count_rub, count_stars FROM payments_agg WHERE id = 1")
            row = await cursor.fetchone()
            if not row:
                return {"total_rub": 0, "total_stars": 0, "count_rub": 0, "count_stars": 0}
            return {
                "total_rub": int(row[0] or 0),
                "total_stars": int(row[1] or 0),
                "count_rub": int(row[2] or 0),
                "count_stars": int(row[3] or 0),
            }

# -------------------------------------------------
# Баланс дней: чтение, начисление, списание
# -------------------------------------------------

async def get_balance_days(tg_id: str) -> int:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT balance FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0


async def add_balance_days(tg_id: str, days: int) -> None:
    if days <= 0:
        return
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT balance FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            if row is None:
                await cursor.execute("INSERT INTO users (tg_id, balance) VALUES (?, ?)", (str(tg_id), int(days)))
            else:
                current_balance = int(row[0]) if row[0] is not None else 0
                await cursor.execute("UPDATE users SET balance = ? WHERE tg_id = ?", (current_balance + int(days), str(tg_id)))
            await conn.commit()


async def deduct_balance_days(tg_id: str, days: int) -> bool:
    if days <= 0:
        return False
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT balance FROM users WHERE tg_id = ?", (str(tg_id),))
            row = await cursor.fetchone()
            current_balance = int(row[0]) if row and row[0] is not None else 0
            if current_balance < days:
                return False
            await cursor.execute("UPDATE users SET balance = ? WHERE tg_id = ?", (current_balance - int(days), str(tg_id)))
            await conn.commit()
            return True

async def build_subscription_kb(user_id: int):
    auth_code = os.getenv("AUTH_CODE", "")
    headers = {"X-API-Key": auth_code} if auth_code else {}
    api_url = f"http://fastapi:8080/sub/{user_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception:
        return None

    sub_key = data.get("sub_key")
    if not sub_key:
        return None

    base = os.getenv("PUBLIC_BASE_URL", "https://swaga.space").rstrip('/')
    web_url = f"{base}/subscription/{sub_key}"
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Добавить подписку в V2rayTun", url=web_url)]
    ])
    return inline_kb


# -----------------------------
# Subscription key helpers
# -----------------------------

async def get_or_create_sub_key(tg_id: str) -> str:
    """Returns a persistent subscription key for the user (idempotent).

    Delegates to the FastAPI backend which stores keys in its DB.
    """
    auth_code = os.getenv("AUTH_CODE", "")
    url = f"http://fastapi:8080/sub/{tg_id}"
    headers = {"X-API-Key": auth_code} if auth_code else {}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                # Propagate for caller to handle fallback if needed
                raise RuntimeError(f"Failed to get sub_key: HTTP {resp.status}")
            data = await resp.json()
            sub_key = data.get("sub_key")
            if not sub_key:
                raise RuntimeError("sub_key missing in response")
            return sub_key