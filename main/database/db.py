import aiosqlite
import time

async def init_db():
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id TEXT,
                user_code TEXT, 
                time_end INTEGER
            )
        ''')
        await conn.commit()

async def insert_into_db(tg_id, user_code, time_end):
    async with aiosqlite.connect("users.db") as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            INSERT INTO users (tg_id, user_code, time_end) VALUES (?, ?, ?)
        ''', (tg_id, user_code, time_end))
        await conn.commit()

async def get_codes_by_tg_id(tg_id):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT user_code, time_end FROM users WHERE tg_id = ?', (tg_id,))
            rows = await cursor.fetchall() 
    
    return rows

async def get_one_expired_client():
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            current_time = int(time.time())
            
            await cursor.execute('''
                SELECT * FROM users WHERE time_end = 0 OR time_end < ?
                LIMIT 1
            ''', (current_time,))
            
            expired_client = await cursor.fetchone()
    
    return expired_client

async def update_user_code(tg_id: str, user_code: str, time_end: int):
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('''
                UPDATE users
                SET tg_id = ?, time_end = ?
                WHERE user_code = ?
            ''', (tg_id, time_end, user_code))
            
            await conn.commit() 
            
            updated_rows = cursor.rowcount
    
    return updated_rows