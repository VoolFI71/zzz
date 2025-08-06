import aiosqlite
import time

country = {
    "fi": "Финляндия",
    "nl": "Нидерланды"
}

async def init_db():
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id TEXT,
                user_code TEXT, 
                time_end INTEGER,
                server_country TEXT NOT NULL
            )
        ''')
        await conn.commit()

async def insert_into_db(tg_id, user_code, time_end, server_country):
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            INSERT INTO users (tg_id, user_code, time_end, server_country) VALUES (?, ?, ?, ?)
        ''', (tg_id, user_code, time_end, server_country))
        await conn.commit()

async def get_codes_by_tg_id(tg_id):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT user_code, time_end, server_country FROM users WHERE tg_id = ?', (tg_id,))
            rows = await cursor.fetchall() 
    
    return rows

async def get_one_expired_client(server_country: str | None = None):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            current_time = int(time.time())
            
            if server_country is None:
                await cursor.execute('''
                    SELECT * FROM users WHERE time_end = 0 OR time_end < ?
                    LIMIT 1
                ''', (current_time,))
            else:
                await cursor.execute('''
                    SELECT * FROM users WHERE (time_end = 0 OR time_end < ?) AND server_country = ?
                    LIMIT 1
                ''', (current_time, server_country))
            
            expired_client = await cursor.fetchone()
    
    return expired_client

async def update_user_code(tg_id: str, user_code: str, time_end: int, server_country: str):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('''
                UPDATE users
                SET tg_id = ?, time_end = ?, server_country = ?
                WHERE user_code = ?
            ''', (tg_id, time_end, server_country, user_code))
            
            await conn.commit() 
            
            updated_rows = cursor.rowcount
    
    return updated_rows

async def get_time_end_by_code(user_code: str):
    """
    Возвращает текущее значение time_end для указанного user_code.
    """
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT time_end FROM users WHERE user_code = ?', (user_code,))
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_time_end(user_code: str, new_time_end: int):
    """
    Устанавливает конкретное значение time_end.
    """
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('''
                UPDATE users
                SET time_end = ?
                WHERE user_code = ?
            ''', (new_time_end, user_code))
            await conn.commit()
            return cursor.rowcount

async def delete_user_code(user_code: str):
    """Удаляет запись конфига из БД по его uid."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('DELETE FROM users WHERE user_code = ?', (user_code,))
            await conn.commit()
            return cursor.rowcount