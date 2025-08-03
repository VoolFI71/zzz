import aiosqlite
import random
import asyncio

async def init_db():
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id TEXT UNIQUE,
                email TEXT,
                referral_code TEXT UNIQUE,
                referred_by TEXT
            )
        ''')
        await conn.commit()
        await cursor.close()  # Закрываем курсор

async def get_email(tg_id):
    """Получить email пользователя по его tg_id из базы данных."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.execute('SELECT email FROM users WHERE tg_id = ?', (tg_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def insert_email(tg_id, email):
    """Сохранить email пользователя в базе данных."""
    try:
        async with aiosqlite.connect("users.db") as conn:
            await cursor.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
            user_data = await cursor.fetchone()
            if user_data:
                # Если запись существует, обновляем email
                await cursor.execute(
                    "UPDATE users SET email=? WHERE tg_id=?",
                    (email, tg_id)
                )
            else:
                # Если записи нет, вставляем новую
                await cursor.execute(
                    "INSERT INTO users (tg_id, email) VALUES (?, ?)",
                    (tg_id, email)
                )
            await conn.commit()
    except aiosqlite.IntegrityError:
        print(f"Ошибка: tg_id '{tg_id}' уже существует.")
    except aiosqlite.Error as e:
        print(f"Ошибка при вставке данных: {e}")

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

async def add_referral_by(user_id, referral_code):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            # Проверяем, существует ли пользователь с таким tg_id
            await cursor.execute("SELECT tg_id FROM users WHERE tg_id = ?", (str(user_id),))
            result = await cursor.fetchone()

            if result is None:
                # Если пользователя нет, вставляем новую запись
                await cursor.execute("INSERT INTO users (tg_id) VALUES (?)", (str(user_id),))

            # Теперь ставим поле referred_by
            await cursor.execute(
                "UPDATE users SET referred_by = ? WHERE tg_id = ?",
                (str(referral_code), str(user_id))
            )
            await conn.commit()


async def get_tg_id_by_referral_code(referral_code):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.execute("SELECT tg_id FROM users WHERE referral_code = ?", (referral_code,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None