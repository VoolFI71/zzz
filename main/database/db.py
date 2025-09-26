import aiosqlite
import time
from typing import Optional
import uuid

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
        # Индексы для ускорения частых операций
        # Уникальность по коду конфига
        await cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_users_user_code ON users(user_code)')
        # Поиск по пользователю
        await cursor.execute('CREATE INDEX IF NOT EXISTS ix_users_tg_id ON users(tg_id)')
        # Массовые операции по истечению срока
        await cursor.execute('CREATE INDEX IF NOT EXISTS ix_users_time_end ON users(time_end)')
        # Быстрый поиск свободных конфигов по стране
        await cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_users_free_by_country
            ON users(server_country, time_end)
            WHERE tg_id IS NULL OR tg_id = ''
            """
        )
        await conn.commit()

        # Таблица ключей подписки: sub_key -> tg_id
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_keys (
                sub_key TEXT PRIMARY KEY,
                tg_id   TEXT NOT NULL
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

async def get_all_user_codes() -> list[tuple[str, str]]:
    """Возвращает все (user_code, server_country) из таблицы users."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT user_code, server_country FROM users')
            rows = await cursor.fetchall()
    return rows

async def get_all_rows() -> list[tuple[str | None, str, int, str]]:
    """Возвращает все строки users как (tg_id, user_code, time_end, server_country)."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('SELECT tg_id, user_code, time_end, server_country FROM users')
            rows = await cursor.fetchall()
    return rows

async def get_one_expired_client(server_country: str | None = None):
    """Возвращает один истекший конфиг (с time_end = 0 или time_end < current_time), независимо от tg_id.
    
    Если server_country is None, возвращает None, так как нельзя выбрать конкретный конфиг
    без указания сервера.
    """
    if server_country is None:
        # Нельзя выбрать конкретный конфиг без указания сервера
        return None
        
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            current_time = int(time.time())
            
            await cursor.execute('''
                SELECT * FROM users
                WHERE (time_end = 0 OR time_end < ?)
                  AND server_country = ?
                LIMIT 1
            ''', (current_time, server_country))
            
            expired_client = await cursor.fetchone()
    
    return expired_client

async def has_any_expired_configs() -> bool:
    """Проверяет, есть ли хотя бы один истекший конфиг на любом сервере."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            current_time = int(time.time())
            
            await cursor.execute('''
                SELECT 1 FROM users
                WHERE (time_end = 0 OR time_end < ?)
                LIMIT 1
            ''', (current_time,))
            
            result = await cursor.fetchone()
            return result is not None

async def reset_expired_configs():
    """
    Сбрасывает tg_id в пустую строку для всех конфигов, у которых истёк срок действия.
    Возвращает количество обновлённых записей.
    """
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            current_time = int(time.time())
            
            await cursor.execute('''
                UPDATE users 
                SET tg_id = '' 
                WHERE time_end > 0 AND time_end < ?
            ''', (current_time,))
            
            await conn.commit()
            return cursor.rowcount

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

async def update_server_country(user_code: str, new_server: str) -> int:
    """Обновляет только поле server_country для указанного user_code."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                '''
                UPDATE users
                SET server_country = ?
                WHERE user_code = ?
                ''',
                (new_server, user_code),
            )
            await conn.commit()
            return cursor.rowcount

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

async def delete_all_user_codes() -> int:
    """Удаляет все конфиги из таблицы `users`. Возвращает количество удалённых строк."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('DELETE FROM users')
            await conn.commit()
            return cursor.rowcount


async def get_tg_id_by_key(sub_key: str) -> Optional[str]:
    """Возвращает tg_id по ключу подписки sub_key или None."""
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                'SELECT tg_id FROM subscription_keys WHERE sub_key = ?',
                (str(sub_key),),
            )
            row = await cursor.fetchone()
            return str(row[0]) if row else None

async def get_sub_key_by_tg_id(tg_id: str) -> Optional[str]:
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                'SELECT sub_key FROM subscription_keys WHERE tg_id = ?',
                (str(tg_id),),
            )
            row = await cursor.fetchone()
            return str(row[0]) if row else None

async def get_or_create_sub_key(tg_id: str) -> str:
    existing = await get_sub_key_by_tg_id(tg_id)
    if existing:
        return existing
    new_key = uuid.uuid4().hex
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                'INSERT OR REPLACE INTO subscription_keys (sub_key, tg_id) VALUES (?, ?)',
                (new_key, str(tg_id)),
            )
            await conn.commit()
    return new_key

RESERVED_PREFIX = "__RESERVED__:" 

async def reserve_one_free_config(
    reserver_tg_id: str,
    server_country: Optional[str] = None,
    reservation_ttl_seconds: int = 60,
) -> Optional[str]:
    """Ищет свободный конфиг и атомарно резервирует его на короткое время.

    Возвращает `user_code` зарезервированного конфига или None, если свободных нет.

    Правила:
    - Свободный: (time_end = 0 OR time_end < now) - независимо от tg_id
    - Резервация: tg_id = "__RESERVED__:{reserver_tg_id}", time_end = now + ttl
    - Перед выбором очищаются просроченные резервации.
    """
    now = int(time.time())
    reservation_expires_at = now + max(5, reservation_ttl_seconds)
    reserved_marker = f"{RESERVED_PREFIX}{reserver_tg_id}"

    async with aiosqlite.connect("users.db") as conn:
        # Не допускаем одновременных писателей
        await conn.execute("BEGIN IMMEDIATE")
        cursor = await conn.cursor()

        # 1) Снять просроченные резервации, чтобы их могли забрать заново
        await cursor.execute(
            '''
            UPDATE users
            SET tg_id = '', time_end = 0
            WHERE tg_id LIKE ? AND time_end > 0 AND time_end < ?
            ''',
            (f"{RESERVED_PREFIX}%", now),
        )

        # 1.1) Освободить истёкшие активные конфиги (с реальным tg_id), чтобы они снова стали доступны
        await cursor.execute(
            '''
            UPDATE users
            SET tg_id = '', time_end = 0
            WHERE time_end > 0 AND time_end < ?
              AND tg_id IS NOT NULL AND tg_id != ''
              AND tg_id NOT LIKE ?
            ''',
            (now, f"{RESERVED_PREFIX}%"),
        )

        # 2) Найти свободный конфиг (с истекшим временем, независимо от tg_id)
        if server_country is None:
            await cursor.execute(
                '''
                SELECT user_code FROM users
                WHERE (time_end = 0 OR time_end < ?)
                LIMIT 1
                ''',
                (now,),
            )
        else:
            await cursor.execute(
                '''
                SELECT user_code FROM users
                WHERE (time_end = 0 OR time_end < ?)
                  AND server_country = ?
                LIMIT 1
                ''',
                (now, server_country),
            )
        row = await cursor.fetchone()
        if row is None:
            await conn.execute("ROLLBACK")
            return None

        uid: str = row[0]

        # 3) Пометить как зарезервированный
        await cursor.execute(
            '''
            UPDATE users
            SET tg_id = ?, time_end = ?
            WHERE user_code = ?
              AND (time_end = 0 OR time_end < ?)
            ''',
            (reserved_marker, reservation_expires_at, uid, now),
        )

        await conn.commit()

        # если кто-то успел между SELECT и UPDATE, rowcount будет 0
        if cursor.rowcount == 0:
            return None

        return uid


async def finalize_reserved_config(
    user_code: str,
    reserver_tg_id: str,
    final_time_end: int,
    server_country: str,
) -> int:
    """Подтверждает ранее сделанную резервацию и выставляет финальные значения.

    Возвращает количество обновлённых строк (1 при успехе, 0 если резервация не найдена/истекла).
    """
    reserved_marker = f"{RESERVED_PREFIX}{reserver_tg_id}"
    now = int(time.time())
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                '''
                UPDATE users
                SET tg_id = ?, time_end = ?, server_country = ?
                WHERE user_code = ?
                  AND tg_id = ?
                ''',
                (str(reserver_tg_id), final_time_end, server_country, user_code, reserved_marker),
            )
            await conn.commit()
            return cursor.rowcount


async def cancel_reserved_config(user_code: str, reserver_tg_id: str) -> int:
    """Снимает резервацию и возвращает конфиг в свободные.

    Возвращает количество обновлённых строк.
    """
    reserved_marker = f"{RESERVED_PREFIX}{reserver_tg_id}"
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                '''
                UPDATE users
                SET tg_id = '', time_end = 0
                WHERE user_code = ? AND tg_id = ?
                ''',
                (user_code, reserved_marker),
            )
            await conn.commit()
            return cursor.rowcount


async def get_all_configs_with_status() -> list[dict]:
    """Возвращает все конфиги с их статусом и информацией.
    
    Возвращает список словарей с полями:
    - uid: user_code (уникальный идентификатор конфига)
    - time_end: время окончания в unix timestamp
    - is_owned: принадлежит ли конфиг кому-то в данный момент
    - server_country: страна сервера
    """
    current_time = int(time.time())
    async with aiosqlite.connect("users.db") as conn:
        async with conn.cursor() as cursor:
            await cursor.execute('''
                SELECT user_code, time_end, tg_id, server_country 
                FROM users 
                ORDER BY time_end ASC
            ''')
            rows = await cursor.fetchall()
    
    configs = []
    for row in rows:
        user_code, time_end, tg_id, server_country = row
        
        # Определяем, принадлежит ли конфиг кому-то (активная привязка только при неистёкшем сроке)
        is_owned = bool(
            tg_id
            and tg_id.strip()
            and not tg_id.startswith(RESERVED_PREFIX)
            and time_end is not None
            and time_end > current_time
        )
        
        configs.append({
            "uid": user_code,
            "time_end": time_end,
            "is_owned": is_owned,
            "server_country": server_country
        })
    
    return configs