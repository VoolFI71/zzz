"""
Продвинутая система рассылок с очередями, батчингом и retry логикой
"""
import asyncio
import logging
import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import aiosqlite
from aiogram import Bot
from aiogram.types import Message
import json

logger = logging.getLogger(__name__)

class BroadcastStatus(Enum):
    PENDING = "pending"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MessageStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BLOCKED = "blocked"

@dataclass
class BroadcastMessage:
    id: str
    user_id: str
    text: str
    parse_mode: Optional[str] = None
    reply_markup: Optional[Dict] = None
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    error_message: Optional[str] = None
    sent_at: Optional[float] = None

@dataclass
class BroadcastCampaign:
    id: str
    name: str
    text: str
    target_segment: str
    status: BroadcastStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_users: int = 0
    sent_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    parse_mode: Optional[str] = None
    reply_markup: Optional[Dict] = None

class BroadcastService:
    def __init__(self, bot: Bot, db_path: str = "users.db"):
        self.bot = bot
        self.db_path = db_path
        self.active_campaigns: Dict[str, BroadcastCampaign] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.batch_size = 10  # Размер батча для отправки
        self.delay_between_batches = 1.0  # Задержка между батчами в секундах
        self.max_retries = 3  # Максимальное количество попыток
        self.retry_delay = 5.0  # Задержка между попытками в секундах
        
    async def init_database(self):
        """Инициализация таблиц для системы рассылок"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    target_segment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    total_users INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    blocked_count INTEGER DEFAULT 0,
                    parse_mode TEXT,
                    reply_markup TEXT
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_messages (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    sent_at REAL,
                    FOREIGN KEY (campaign_id) REFERENCES broadcast_campaigns (id)
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_segments (
                    user_id TEXT PRIMARY KEY,
                    segment TEXT NOT NULL,
                    last_activity REAL,
                    subscription_status TEXT,
                    payment_count INTEGER DEFAULT 0,
                    referral_count INTEGER DEFAULT 0,
                    created_at REAL
                )
            """)
            
            await conn.commit()

    async def create_campaign(
        self, 
        name: str, 
        text: str, 
        target_segment: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict] = None
    ) -> str:
        """Создание новой кампании рассылки"""
        campaign_id = f"campaign_{int(time.time())}_{hash(name) % 10000}"
        
        campaign = BroadcastCampaign(
            id=campaign_id,
            name=name,
            text=text,
            target_segment=target_segment,
            status=BroadcastStatus.PENDING,
            created_at=time.time(),
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        
        # Сохраняем кампанию в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO broadcast_campaigns 
                (id, name, text, target_segment, status, created_at, parse_mode, reply_markup)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign_id, name, text, target_segment, 
                BroadcastStatus.PENDING.value, time.time(),
                parse_mode, json.dumps(reply_markup) if reply_markup else None
            ))
            await conn.commit()
        
        self.active_campaigns[campaign_id] = campaign
        return campaign_id

    async def get_users_by_segment(self, segment: str) -> List[str]:
        """Получение пользователей по сегменту"""
        segments = {
            "all": "SELECT tg_id FROM users",
            "active": "SELECT tg_id FROM users WHERE balance > 0",
            "trial_only": """
                SELECT tg_id FROM users 
                WHERE trial_3d_used = 1 AND (paid_count IS NULL OR paid_count = 0)
            """,
            "expired": """
                SELECT tg_id FROM users 
                WHERE balance <= 0 AND (trial_3d_used = 1 OR paid_count > 0)
            """,
            "no_subscription": "SELECT tg_id FROM users WHERE balance <= 0",
            "with_referrals": "SELECT tg_id FROM users WHERE referral_count > 0",
            "vip": "SELECT tg_id FROM users WHERE paid_count >= 5"
        }
        
        if segment not in segments:
            logger.warning(f"Unknown segment: {segment}")
            return []
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(segments[segment])
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]

    async def start_campaign(self, campaign_id: str) -> bool:
        """Запуск кампании рассылки"""
        if campaign_id not in self.active_campaigns:
            logger.error(f"Campaign {campaign_id} not found")
            return False
        
        campaign = self.active_campaigns[campaign_id]
        if campaign.status != BroadcastStatus.PENDING:
            logger.error(f"Campaign {campaign_id} is not in pending status")
            return False
        
        # Получаем пользователей для рассылки
        user_ids = await self.get_users_by_segment(campaign.target_segment)
        if not user_ids:
            logger.warning(f"No users found for segment: {campaign.target_segment}")
            return False
        
        campaign.total_users = len(user_ids)
        campaign.status = BroadcastStatus.SENDING
        campaign.started_at = time.time()
        
        # Обновляем статус в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE broadcast_campaigns 
                SET status = ?, started_at = ?, total_users = ?
                WHERE id = ?
            """, (BroadcastStatus.SENDING.value, campaign.started_at, campaign.total_users, campaign_id))
            await conn.commit()
        
        # Создаем сообщения для очереди
        await self._create_messages_for_campaign(campaign_id, user_ids)
        
        # Запускаем обработку очереди, если она не запущена
        if not self.is_running:
            asyncio.create_task(self._process_queue())
        
        return True

    async def _create_messages_for_campaign(self, campaign_id: str, user_ids: List[str]):
        """Создание сообщений для кампании"""
        campaign = self.active_campaigns[campaign_id]
        
        async with aiosqlite.connect(self.db_path) as conn:
            for user_id in user_ids:
                message_id = f"msg_{campaign_id}_{user_id}_{int(time.time())}"
                
                await conn.execute("""
                    INSERT INTO broadcast_messages 
                    (id, campaign_id, user_id, text, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (message_id, campaign_id, user_id, campaign.text, MessageStatus.PENDING.value))
                
                # Добавляем в очередь
                message = BroadcastMessage(
                    id=message_id,
                    user_id=user_id,
                    text=campaign.text,
                    parse_mode=campaign.parse_mode,
                    reply_markup=campaign.reply_markup
                )
                await self.message_queue.put(message)
            
            await conn.commit()

    async def _process_queue(self):
        """Обработка очереди сообщений"""
        self.is_running = True
        logger.info("Starting broadcast queue processing")
        
        while self.is_running:
            try:
                # Получаем батч сообщений
                batch = []
                for _ in range(self.batch_size):
                    try:
                        message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                        batch.append(message)
                    except asyncio.TimeoutError:
                        break
                
                if not batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # Отправляем батч
                await self._send_batch(batch)
                
                # Задержка между батчами
                await asyncio.sleep(self.delay_between_batches)
                
            except Exception as e:
                logger.error(f"Error processing broadcast queue: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("Broadcast queue processing stopped")

    async def _send_batch(self, batch: List[BroadcastMessage]):
        """Отправка батча сообщений"""
        tasks = []
        for message in batch:
            task = asyncio.create_task(self._send_single_message(message))
            tasks.append(task)
        
        # Ждем завершения всех задач в батче
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_single_message(self, message: BroadcastMessage):
        """Отправка одного сообщения с retry логикой"""
        try:
            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=message.user_id,
                text=message.text,
                parse_mode=message.parse_mode,
                reply_markup=message.reply_markup
            )
            
            # Обновляем статус
            message.status = MessageStatus.SENT
            message.sent_at = time.time()
            
            # Обновляем в БД
            await self._update_message_status(message)
            
            # Обновляем статистику кампании
            await self._update_campaign_stats(message.campaign_id, "sent")
            
            logger.info(f"Message sent successfully to user {message.user_id}")
            
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Failed to send message to {message.user_id}: {error_msg}")
            
            message.retry_count += 1
            message.error_message = error_msg
            
            if message.retry_count < self.max_retries:
                # Добавляем обратно в очередь для повторной попытки
                await asyncio.sleep(self.retry_delay)
                await self.message_queue.put(message)
            else:
                # Максимальное количество попыток исчерпано
                if "blocked" in error_msg.lower() or "forbidden" in error_msg.lower():
                    message.status = MessageStatus.BLOCKED
                    await self._update_campaign_stats(message.campaign_id, "blocked")
                else:
                    message.status = MessageStatus.FAILED
                    await self._update_campaign_stats(message.campaign_id, "failed")
                
                await self._update_message_status(message)

    async def _update_message_status(self, message: BroadcastMessage):
        """Обновление статуса сообщения в БД"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE broadcast_messages 
                SET status = ?, retry_count = ?, error_message = ?, sent_at = ?
                WHERE id = ?
            """, (
                message.status.value, message.retry_count, 
                message.error_message, message.sent_at, message.id
            ))
            await conn.commit()

    async def _update_campaign_stats(self, campaign_id: str, action: str):
        """Обновление статистики кампании"""
        if campaign_id not in self.active_campaigns:
            return
        
        campaign = self.active_campaigns[campaign_id]
        
        if action == "sent":
            campaign.sent_count += 1
        elif action == "failed":
            campaign.failed_count += 1
        elif action == "blocked":
            campaign.blocked_count += 1
        
        # Проверяем, завершена ли кампания
        total_processed = campaign.sent_count + campaign.failed_count + campaign.blocked_count
        if total_processed >= campaign.total_users:
            campaign.status = BroadcastStatus.COMPLETED
            campaign.completed_at = time.time()
            
            # Обновляем в БД
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    UPDATE broadcast_campaigns 
                    SET status = ?, completed_at = ?, sent_count = ?, failed_count = ?, blocked_count = ?
                    WHERE id = ?
                """, (
                    BroadcastStatus.COMPLETED.value, campaign.completed_at,
                    campaign.sent_count, campaign.failed_count, campaign.blocked_count, campaign_id
                ))
                await conn.commit()
            
            logger.info(f"Campaign {campaign_id} completed: {campaign.sent_count} sent, {campaign.failed_count} failed, {campaign.blocked_count} blocked")

    async def get_campaign_stats(self, campaign_id: str) -> Optional[Dict]:
        """Получение статистики кампании"""
        if campaign_id not in self.active_campaigns:
            return None
        
        campaign = self.active_campaigns[campaign_id]
        return {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status.value,
            "total_users": campaign.total_users,
            "sent_count": campaign.sent_count,
            "failed_count": campaign.failed_count,
            "blocked_count": campaign.blocked_count,
            "progress": (campaign.sent_count + campaign.failed_count + campaign.blocked_count) / campaign.total_users * 100 if campaign.total_users > 0 else 0
        }

    async def stop_campaign(self, campaign_id: str) -> bool:
        """Остановка кампании"""
        if campaign_id not in self.active_campaigns:
            return False
        
        campaign = self.active_campaigns[campaign_id]
        if campaign.status != BroadcastStatus.SENDING:
            return False
        
        campaign.status = BroadcastStatus.CANCELLED
        campaign.completed_at = time.time()
        
        # Обновляем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE broadcast_campaigns 
                SET status = ?, completed_at = ?
                WHERE id = ?
            """, (BroadcastStatus.CANCELLED.value, campaign.completed_at, campaign_id))
            await conn.commit()
        
        return True

    async def stop_all_campaigns(self):
        """Остановка всех кампаний"""
        for campaign_id in list(self.active_campaigns.keys()):
            await self.stop_campaign(campaign_id)
        
        self.is_running = False

