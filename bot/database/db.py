import aiosqlite
import random
import asyncio

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
                    trial_3d_used INTEGER DEFAULT 0
                )
            ''')
            await conn.commit()

user_locks = {}
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

async def add_referral_by(user_id, referral_code, max_invites: int = 7) -> bool:
    """Добавляет связь реферала и увеличивает счётчик, если лимит не достигнут.

    Возвращает True, если бонус следует начислить (счётчик < max_invites),
    False – если лимит был исчерпан и счётчик не изменён."""
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

            if current_count >= max_invites:
                # Лимит достигнут – просто фиксируем referral, но без бонуса
                await conn.commit()
                return False

            # 3. Увеличиваем счётчик
            await cursor.execute(
                "UPDATE users SET referral_count = ? WHERE referral_code = ?",
                (current_count + 1, str(referral_code))
            )
            await conn.commit()
            return True

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