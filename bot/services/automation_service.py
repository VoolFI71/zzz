"""
Система автоматизации: scheduled tasks, drip campaigns, smart targeting
"""
import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import aiosqlite
import random

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(Enum):
    BROADCAST = "broadcast"
    REMINDER = "reminder"
    CLEANUP = "cleanup"
    ANALYTICS = "analytics"
    MAINTENANCE = "maintenance"

@dataclass
class ScheduledTask:
    id: str
    name: str
    task_type: TaskType
    status: TaskStatus
    schedule_time: float
    interval_seconds: Optional[int] = None  # Для повторяющихся задач
    parameters: Dict[str, Any] = None
    created_at: float = 0
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class DripCampaign:
    id: str
    name: str
    target_segment: str
    messages: List[Dict[str, Any]]  # Список сообщений с задержками
    is_active: bool = True
    created_at: float = 0
    total_users: int = 0
    completed_users: int = 0

@dataclass
class SmartTargetingRule:
    id: str
    name: str
    conditions: List[Dict[str, Any]]  # Условия для сегментации
    action: str  # Действие при срабатывании
    parameters: Dict[str, Any] = None
    is_active: bool = True
    created_at: float = 0
    trigger_count: int = 0

class AutomationService:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.drip_campaigns: Dict[str, DripCampaign] = {}
        self.smart_rules: Dict[str, SmartTargetingRule] = {}
        self.is_running = False
        self.task_handlers: Dict[TaskType, Callable] = {}
        
    async def init_database(self):
        """Инициализация таблиц для автоматизации"""
        async with aiosqlite.connect(self.db_path) as conn:
            # Таблица запланированных задач
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    schedule_time REAL NOT NULL,
                    interval_seconds INTEGER,
                    parameters TEXT,
                    created_at REAL NOT NULL,
                    last_run REAL,
                    next_run REAL,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3
                )
            """)
            
            # Таблица drip кампаний
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS drip_campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    target_segment TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    total_users INTEGER DEFAULT 0,
                    completed_users INTEGER DEFAULT 0
                )
            """)
            
            # Таблица пользователей в drip кампаниях
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS drip_campaign_users (
                    campaign_id TEXT,
                    user_id TEXT,
                    current_message_index INTEGER DEFAULT 0,
                    next_send_time REAL,
                    is_completed INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (campaign_id, user_id),
                    FOREIGN KEY (campaign_id) REFERENCES drip_campaigns (id)
                )
            """)
            
            # Таблица умных правил
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS smart_targeting_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    conditions TEXT NOT NULL,
                    action TEXT NOT NULL,
                    parameters TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    trigger_count INTEGER DEFAULT 0
                )
            """)
            
            await conn.commit()
    
    async def start_automation(self):
        """Запуск системы автоматизации"""
        if self.is_running:
            return
        
        self.is_running = True
        await self._load_tasks_from_db()
        asyncio.create_task(self._automation_loop())
        logger.info("Automation service started")
    
    async def stop_automation(self):
        """Остановка системы автоматизации"""
        self.is_running = False
        logger.info("Automation service stopped")
    
    async def _automation_loop(self):
        """Основной цикл автоматизации"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Обрабатываем запланированные задачи
                await self._process_scheduled_tasks(current_time)
                
                # Обрабатываем drip кампании
                await self._process_drip_campaigns(current_time)
                
                # Проверяем умные правила
                await self._check_smart_rules(current_time)
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                await asyncio.sleep(10)
    
    async def _load_tasks_from_db(self):
        """Загрузка задач из базы данных"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, name, task_type, status, schedule_time, interval_seconds,
                           parameters, created_at, last_run, next_run, retry_count, max_retries
                    FROM scheduled_tasks
                    WHERE status IN ('pending', 'running')
                """)
                tasks = await cursor.fetchall()
                
                for task_data in tasks:
                    task = ScheduledTask(
                        id=task_data[0],
                        name=task_data[1],
                        task_type=TaskType(task_data[2]),
                        status=TaskStatus(task_data[3]),
                        schedule_time=task_data[4],
                        interval_seconds=task_data[5],
                        parameters=json.loads(task_data[6]) if task_data[6] else {},
                        created_at=task_data[7],
                        last_run=task_data[8],
                        next_run=task_data[9],
                        retry_count=task_data[10],
                        max_retries=task_data[11]
                    )
                    self.scheduled_tasks[task.id] = task
    
    async def _process_scheduled_tasks(self, current_time: float):
        """Обработка запланированных задач"""
        for task_id, task in list(self.scheduled_tasks.items()):
            if task.status != TaskStatus.PENDING:
                continue
            
            # Проверяем, пора ли выполнять задачу
            if current_time >= task.schedule_time:
                await self._execute_task(task)
    
    async def _execute_task(self, task: ScheduledTask):
        """Выполнение задачи"""
        task.status = TaskStatus.RUNNING
        task.last_run = time.time()
        
        try:
            # Обновляем статус в БД
            await self._update_task_status(task)
            
            # Выполняем задачу
            if task.task_type in self.task_handlers:
                await self.task_handlers[task.task_type](task.parameters)
                task.status = TaskStatus.COMPLETED
            else:
                logger.warning(f"No handler for task type: {task.task_type}")
                task.status = TaskStatus.FAILED
            
            # Если задача повторяющаяся, планируем следующее выполнение
            if task.interval_seconds and task.status == TaskStatus.COMPLETED:
                task.next_run = time.time() + task.interval_seconds
                task.status = TaskStatus.PENDING
                task.schedule_time = task.next_run
            
        except Exception as e:
            logger.error(f"Error executing task {task.id}: {e}")
            task.retry_count += 1
            
            if task.retry_count >= task.max_retries:
                task.status = TaskStatus.FAILED
            else:
                task.status = TaskStatus.PENDING
                task.schedule_time = time.time() + (60 * task.retry_count)  # Экспоненциальная задержка
        
        await self._update_task_status(task)
    
    async def _update_task_status(self, task: ScheduledTask):
        """Обновление статуса задачи в БД"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE scheduled_tasks 
                SET status = ?, last_run = ?, next_run = ?, retry_count = ?
                WHERE id = ?
            """, (task.status.value, task.last_run, task.next_run, task.retry_count, task.id))
            await conn.commit()
    
    async def create_scheduled_task(
        self,
        name: str,
        task_type: TaskType,
        schedule_time: float,
        parameters: Dict[str, Any] = None,
        interval_seconds: Optional[int] = None,
        max_retries: int = 3
    ) -> str:
        """Создание запланированной задачи"""
        task_id = f"task_{int(time.time())}_{hash(name) % 10000}"
        
        task = ScheduledTask(
            id=task_id,
            name=name,
            task_type=task_type,
            status=TaskStatus.PENDING,
            schedule_time=schedule_time,
            interval_seconds=interval_seconds,
            parameters=parameters or {},
            created_at=time.time(),
            max_retries=max_retries
        )
        
        # Сохраняем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO scheduled_tasks 
                (id, name, task_type, status, schedule_time, interval_seconds, 
                 parameters, created_at, max_retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, name, task_type.value, TaskStatus.PENDING.value,
                schedule_time, interval_seconds, json.dumps(parameters or {}),
                time.time(), max_retries
            ))
            await conn.commit()
        
        self.scheduled_tasks[task_id] = task
        return task_id
    
    async def create_drip_campaign(
        self,
        name: str,
        target_segment: str,
        messages: List[Dict[str, Any]]
    ) -> str:
        """Создание drip кампании"""
        campaign_id = f"drip_{int(time.time())}_{hash(name) % 10000}"
        
        campaign = DripCampaign(
            id=campaign_id,
            name=name,
            target_segment=target_segment,
            messages=messages,
            created_at=time.time()
        )
        
        # Сохраняем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO drip_campaigns 
                (id, name, target_segment, messages, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (campaign_id, name, target_segment, json.dumps(messages), time.time()))
            await conn.commit()
        
        self.drip_campaigns[campaign_id] = campaign
        return campaign_id
    
    async def start_drip_campaign(self, campaign_id: str) -> bool:
        """Запуск drip кампании"""
        if campaign_id not in self.drip_campaigns:
            return False
        
        campaign = self.drip_campaigns[campaign_id]
        if not campaign.is_active:
            return False
        
        # Получаем пользователей для сегмента
        user_ids = await self._get_users_by_segment(campaign.target_segment)
        campaign.total_users = len(user_ids)
        
        # Добавляем пользователей в кампанию
        async with aiosqlite.connect(self.db_path) as conn:
            for user_id in user_ids:
                await conn.execute("""
                    INSERT OR IGNORE INTO drip_campaign_users 
                    (campaign_id, user_id, next_send_time, created_at)
                    VALUES (?, ?, ?, ?)
                """, (campaign_id, user_id, time.time(), time.time()))
            await conn.commit()
        
        return True
    
    async def _process_drip_campaigns(self, current_time: float):
        """Обработка drip кампаний"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT dcu.campaign_id, dcu.user_id, dcu.current_message_index, 
                           dcu.next_send_time, dc.messages
                    FROM drip_campaign_users dcu
                    JOIN drip_campaigns dc ON dcu.campaign_id = dc.id
                    WHERE dcu.is_completed = 0 AND dcu.next_send_time <= ?
                """, (current_time,))
                
                users_to_process = await cursor.fetchall()
                
                for campaign_id, user_id, message_index, next_send_time, messages_json in users_to_process:
                    messages = json.loads(messages_json)
                    
                    if message_index < len(messages):
                        message_data = messages[message_index]
                        await self._send_drip_message(campaign_id, user_id, message_data)
                        
                        # Обновляем индекс и время следующей отправки
                        next_message_index = message_index + 1
                        is_completed = next_message_index >= len(messages)
                        
                        if is_completed:
                            next_send_time = None
                        else:
                            delay_hours = messages[next_message_index].get("delay_hours", 24)
                            next_send_time = current_time + (delay_hours * 3600)
                        
                        await cursor.execute("""
                            UPDATE drip_campaign_users 
                            SET current_message_index = ?, next_send_time = ?, is_completed = ?
                            WHERE campaign_id = ? AND user_id = ?
                        """, (next_message_index, next_send_time, is_completed, campaign_id, user_id))
                
                await conn.commit()
    
    async def _send_drip_message(self, campaign_id: str, user_id: str, message_data: Dict[str, Any]):
        """Отправка сообщения drip кампании"""
        # Здесь должна быть логика отправки сообщения через бота
        # Пока просто логируем
        logger.info(f"Sending drip message to user {user_id} in campaign {campaign_id}")
    
    async def _get_users_by_segment(self, segment: str) -> List[str]:
        """Получение пользователей по сегменту"""
        segments = {
            "all": "SELECT tg_id FROM users",
            "active": "SELECT tg_id FROM users WHERE balance > 0",
            "trial_only": "SELECT tg_id FROM users WHERE trial_3d_used = 1 AND (paid_count IS NULL OR paid_count = 0)",
            "expired": "SELECT tg_id FROM users WHERE balance <= 0 AND (trial_3d_used = 1 OR paid_count > 0)",
            "no_subscription": "SELECT tg_id FROM users WHERE balance <= 0",
            "with_referrals": "SELECT tg_id FROM users WHERE referral_count > 0",
            "vip": "SELECT tg_id FROM users WHERE paid_count >= 5"
        }
        
        if segment not in segments:
            return []
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(segments[segment])
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]
    
    async def create_smart_rule(
        self,
        name: str,
        conditions: List[Dict[str, Any]],
        action: str,
        parameters: Dict[str, Any] = None
    ) -> str:
        """Создание умного правила"""
        rule_id = f"rule_{int(time.time())}_{hash(name) % 10000}"
        
        rule = SmartTargetingRule(
            id=rule_id,
            name=name,
            conditions=conditions,
            action=action,
            parameters=parameters or {},
            created_at=time.time()
        )
        
        # Сохраняем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO smart_targeting_rules 
                (id, name, conditions, action, parameters, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rule_id, name, json.dumps(conditions), action, json.dumps(parameters or {}), time.time()))
            await conn.commit()
        
        self.smart_rules[rule_id] = rule
        return rule_id
    
    async def _check_smart_rules(self, current_time: float):
        """Проверка умных правил"""
        for rule_id, rule in self.smart_rules.items():
            if not rule.is_active:
                continue
            
            try:
                # Проверяем условия правила
                if await self._evaluate_rule_conditions(rule):
                    await self._execute_rule_action(rule)
                    rule.trigger_count += 1
                    
                    # Обновляем счетчик в БД
                    async with aiosqlite.connect(self.db_path) as conn:
                        await conn.execute("""
                            UPDATE smart_targeting_rules 
                            SET trigger_count = ?
                            WHERE id = ?
                        """, (rule.trigger_count, rule_id))
                        await conn.commit()
            
            except Exception as e:
                logger.error(f"Error checking smart rule {rule_id}: {e}")
    
    async def _evaluate_rule_conditions(self, rule: SmartTargetingRule) -> bool:
        """Оценка условий правила"""
        # Здесь должна быть логика оценки условий
        # Пока возвращаем случайное значение для демонстрации
        return random.random() < 0.1  # 10% вероятность срабатывания
    
    async def _execute_rule_action(self, rule: SmartTargetingRule):
        """Выполнение действия правила"""
        logger.info(f"Executing smart rule action: {rule.action}")
        # Здесь должна быть логика выполнения действия
    
    def register_task_handler(self, task_type: TaskType, handler: Callable):
        """Регистрация обработчика задач"""
        self.task_handlers[task_type] = handler
    
    async def get_automation_stats(self) -> Dict[str, Any]:
        """Получение статистики автоматизации"""
        return {
            "is_running": self.is_running,
            "scheduled_tasks": len(self.scheduled_tasks),
            "drip_campaigns": len(self.drip_campaigns),
            "smart_rules": len(self.smart_rules),
            "active_tasks": len([t for t in self.scheduled_tasks.values() if t.status == TaskStatus.PENDING]),
            "completed_tasks": len([t for t in self.scheduled_tasks.values() if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.scheduled_tasks.values() if t.status == TaskStatus.FAILED])
        }




