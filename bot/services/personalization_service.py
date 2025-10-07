"""
Сервис персонализации и улучшения пользовательского опыта
"""
import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import aiosqlite
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class UserSegment(Enum):
    NEW_USER = "new_user"
    TRIAL_USER = "trial_user"
    ACTIVE_SUBSCRIBER = "active_subscriber"
    EXPIRED_SUBSCRIBER = "expired_subscriber"
    VIP_USER = "vip_user"
    INACTIVE_USER = "inactive_user"

class NotificationType(Enum):
    WELCOME = "welcome"
    TRIAL_REMINDER = "trial_reminder"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    PAYMENT_SUCCESS = "payment_success"
    REFERRAL_BONUS = "referral_bonus"
    PROMOTION = "promotion"
    MAINTENANCE = "maintenance"

@dataclass
class UserProfile:
    user_id: str
    segment: UserSegment
    preferences: Dict[str, Any]
    last_activity: float
    subscription_status: str
    payment_history: List[Dict[str, Any]]
    referral_stats: Dict[str, int]
    engagement_score: float
    created_at: float

@dataclass
class PersonalizedMessage:
    user_id: str
    message_type: NotificationType
    content: str
    personalization_data: Dict[str, Any]
    priority: int
    scheduled_time: float
    is_sent: bool = False

@dataclass
class SmartNotification:
    id: str
    user_id: str
    notification_type: NotificationType
    content: str
    personalization: Dict[str, Any]
    priority: int
    created_at: float
    scheduled_time: float
    is_sent: bool = False
    sent_at: Optional[float] = None

class PersonalizationService:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.user_profiles: Dict[str, UserProfile] = {}
        self.smart_notifications: List[SmartNotification] = []
        self.personalization_rules: Dict[str, Dict[str, Any]] = {}
        self.is_running = False
        
    async def init_database(self):
        """Инициализация таблиц для персонализации"""
        async with aiosqlite.connect(self.db_path) as conn:
            # Таблица пользовательских профилей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    segment TEXT NOT NULL,
                    preferences TEXT,
                    last_activity REAL,
                    subscription_status TEXT,
                    payment_history TEXT,
                    referral_stats TEXT,
                    engagement_score REAL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            # Таблица умных уведомлений
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS smart_notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    personalization TEXT,
                    priority INTEGER DEFAULT 5,
                    created_at REAL NOT NULL,
                    scheduled_time REAL NOT NULL,
                    is_sent INTEGER DEFAULT 0,
                    sent_at REAL
                )
            """)
            
            # Таблица правил персонализации
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS personalization_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    conditions TEXT NOT NULL,
                    actions TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    trigger_count INTEGER DEFAULT 0
                )
            """)
            
            await conn.commit()
    
    async def start_personalization(self):
        """Запуск сервиса персонализации"""
        if self.is_running:
            return
        
        self.is_running = True
        await self._load_user_profiles()
        await self._load_personalization_rules()
        asyncio.create_task(self._personalization_loop())
        logger.info("Personalization service started")
    
    async def stop_personalization(self):
        """Остановка сервиса персонализации"""
        self.is_running = False
        logger.info("Personalization service stopped")
    
    async def _personalization_loop(self):
        """Основной цикл персонализации"""
        while self.is_running:
            try:
                # Обновляем профили пользователей
                await self._update_user_profiles()
                
                # Генерируем умные уведомления
                await self._generate_smart_notifications()
                
                # Отправляем запланированные уведомления
                await self._send_scheduled_notifications()
                
                # Применяем правила персонализации
                await self._apply_personalization_rules()
                
                await asyncio.sleep(300)  # Проверяем каждые 5 минут
                
            except Exception as e:
                logger.error(f"Error in personalization loop: {e}")
                await asyncio.sleep(60)
    
    async def _load_user_profiles(self):
        """Загрузка профилей пользователей"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT user_id, segment, preferences, last_activity, subscription_status,
                           payment_history, referral_stats, engagement_score, created_at
                    FROM user_profiles
                """)
                profiles = await cursor.fetchall()
                
                for profile_data in profiles:
                    profile = UserProfile(
                        user_id=profile_data[0],
                        segment=UserSegment(profile_data[1]),
                        preferences=json.loads(profile_data[2]) if profile_data[2] else {},
                        last_activity=profile_data[3],
                        subscription_status=profile_data[4],
                        payment_history=json.loads(profile_data[5]) if profile_data[5] else [],
                        referral_stats=json.loads(profile_data[6]) if profile_data[6] else {},
                        engagement_score=profile_data[7],
                        created_at=profile_data[8]
                    )
                    self.user_profiles[profile.user_id] = profile
    
    async def _load_personalization_rules(self):
        """Загрузка правил персонализации"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, name, conditions, actions, is_active, trigger_count
                    FROM personalization_rules
                    WHERE is_active = 1
                """)
                rules = await cursor.fetchall()
                
                for rule_data in rules:
                    rule_id = rule_data[0]
                    self.personalization_rules[rule_id] = {
                        "name": rule_data[1],
                        "conditions": json.loads(rule_data[2]),
                        "actions": json.loads(rule_data[3]),
                        "trigger_count": rule_data[5]
                    }
    
    async def _update_user_profiles(self):
        """Обновление профилей пользователей"""
        current_time = time.time()
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                # Получаем всех пользователей
                await cursor.execute("""
                    SELECT tg_id, balance, trial_3d_used, paid_count, referral_count, 
                           last_payment_at, created_at
                    FROM users
                """)
                users = await cursor.fetchall()
                
                for user_data in users:
                    user_id, balance, trial_used, paid_count, referral_count, last_payment, created_at = user_data
                    
                    # Определяем сегмент пользователя
                    segment = await self._determine_user_segment(
                        balance, trial_used, paid_count, referral_count, last_payment, created_at
                    )
                    
                    # Вычисляем engagement score
                    engagement_score = await self._calculate_engagement_score(user_id)
                    
                    # Обновляем или создаем профиль
                    await cursor.execute("""
                        INSERT OR REPLACE INTO user_profiles 
                        (user_id, segment, last_activity, subscription_status, engagement_score, 
                         created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user_id, segment.value, current_time, 
                        "active" if balance > 0 else "inactive",
                        engagement_score, created_at, current_time
                    ))
                
                await conn.commit()
    
    async def _determine_user_segment(
        self, balance: int, trial_used: int, paid_count: int, 
        referral_count: int, last_payment: float, created_at: float
    ) -> UserSegment:
        """Определение сегмента пользователя"""
        current_time = time.time()
        
        # VIP пользователи (5+ платежей)
        if paid_count >= 5:
            return UserSegment.VIP_USER
        
        # Активные подписчики
        if balance > 0:
            return UserSegment.ACTIVE_SUBSCRIBER
        
        # Пользователи с истекшей подпиской
        if trial_used == 1 or paid_count > 0:
            return UserSegment.EXPIRED_SUBSCRIBER
        
        # Пробные пользователи
        if trial_used == 1:
            return UserSegment.TRIAL_USER
        
        # Новые пользователи
        if current_time - created_at < 7 * 24 * 60 * 60:  # Менее недели
            return UserSegment.NEW_USER
        
        # Неактивные пользователи
        if current_time - last_payment > 30 * 24 * 60 * 60:  # Более месяца без активности
            return UserSegment.INACTIVE_USER
        
        return UserSegment.NEW_USER
    
    async def _calculate_engagement_score(self, user_id: str) -> float:
        """Вычисление engagement score пользователя"""
        # Базовая логика для вычисления engagement score
        # В реальном проекте здесь должна быть более сложная логика
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                # Количество платежей
                await cursor.execute("SELECT paid_count FROM users WHERE tg_id = ?", (user_id,))
                paid_count = (await cursor.fetchone())[0] or 0
                
                # Количество рефералов
                await cursor.execute("SELECT referral_count FROM users WHERE tg_id = ?", (user_id,))
                referral_count = (await cursor.fetchone())[0] or 0
                
                # Время с последней активности
                await cursor.execute("SELECT last_payment_at FROM users WHERE tg_id = ?", (user_id,))
                last_payment = (await cursor.fetchone())[0] or 0
                
                current_time = time.time()
                days_since_activity = (current_time - last_payment) / (24 * 60 * 60) if last_payment > 0 else 365
                
                # Вычисляем score
                score = 0.0
                score += min(paid_count * 0.2, 1.0)  # До 1.0 за платежи
                score += min(referral_count * 0.1, 0.5)  # До 0.5 за рефералов
                score += max(0, 1.0 - (days_since_activity / 30))  # Штраф за неактивность
                
                return min(max(score, 0.0), 1.0)
    
    async def _generate_smart_notifications(self):
        """Генерация умных уведомлений"""
        current_time = time.time()
        
        # Проверяем различные условия для генерации уведомлений
        await self._check_trial_reminders()
        await self._check_subscription_expiring()
        await self._check_subscription_expired()
        await self._check_promotional_opportunities()
    
    async def _check_trial_reminders(self):
        """Проверка напоминаний о пробной подписке"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                # Пользователи с пробной подпиской, которым нужно напомнить
                await cursor.execute("""
                    SELECT tg_id FROM users 
                    WHERE trial_3d_used = 1 AND (paid_count IS NULL OR paid_count = 0)
                    AND created_at < ? - 2 * 24 * 60 * 60
                """, (time.time(),))
                trial_users = await cursor.fetchall()
                
                for user_data in trial_users:
                    user_id = user_data[0]
                    await self._create_smart_notification(
                        user_id, NotificationType.TRIAL_REMINDER,
                        "Не забудьте попробовать наш VPN! У вас есть бесплатные 3 дня.",
                        {"segment": "trial_user", "urgency": "medium"},
                        priority=3
                    )
    
    async def _check_subscription_expiring(self):
        """Проверка истекающих подписок"""
        # Здесь должна быть логика проверки через API
        pass
    
    async def _check_subscription_expired(self):
        """Проверка истекших подписок"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                # Пользователи с истекшей подпиской
                await cursor.execute("""
                    SELECT tg_id FROM users 
                    WHERE balance <= 0 AND (trial_3d_used = 1 OR paid_count > 0)
                """)
                expired_users = await cursor.fetchall()
                
                for user_data in expired_users:
                    user_id = user_data[0]
                    await self._create_smart_notification(
                        user_id, NotificationType.SUBSCRIPTION_EXPIRED,
                        "Ваша подписка истекла. Продлите доступ к VPN!",
                        {"segment": "expired_subscriber", "urgency": "high"},
                        priority=1
                    )
    
    async def _check_promotional_opportunities(self):
        """Проверка возможностей для промо-акций"""
        # Логика для определения промо-возможностей
        pass
    
    async def _create_smart_notification(
        self, user_id: str, notification_type: NotificationType,
        content: str, personalization: Dict[str, Any], priority: int = 5
    ):
        """Создание умного уведомления"""
        notification_id = f"notif_{int(time.time())}_{hash(f'{user_id}_{notification_type.value}') % 10000}"
        
        # Определяем время отправки на основе приоритета
        delay_minutes = {1: 0, 2: 5, 3: 15, 4: 60, 5: 240}  # Приоритет -> задержка в минутах
        scheduled_time = time.time() + (delay_minutes.get(priority, 240) * 60)
        
        notification = SmartNotification(
            id=notification_id,
            user_id=user_id,
            notification_type=notification_type,
            content=content,
            personalization=personalization,
            priority=priority,
            created_at=time.time(),
            scheduled_time=scheduled_time
        )
        
        # Сохраняем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO smart_notifications 
                (id, user_id, notification_type, content, personalization, priority, 
                 created_at, scheduled_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_id, user_id, notification_type.value, content,
                json.dumps(personalization), priority, time.time(), scheduled_time
            ))
            await conn.commit()
        
        self.smart_notifications.append(notification)
    
    async def _send_scheduled_notifications(self):
        """Отправка запланированных уведомлений"""
        current_time = time.time()
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, user_id, notification_type, content, personalization
                    FROM smart_notifications 
                    WHERE is_sent = 0 AND scheduled_time <= ?
                    ORDER BY priority ASC, scheduled_time ASC
                    LIMIT 10
                """, (current_time,))
                
                notifications = await cursor.fetchall()
                
                for notif_data in notifications:
                    notification_id, user_id, notif_type, content, personalization = notif_data
                    
                    # Персонализируем сообщение
                    personalized_content = await self._personalize_message(
                        user_id, content, json.loads(personalization)
                    )
                    
                    # Отправляем уведомление (здесь должна быть логика отправки через бота)
                    await self._send_notification_to_user(user_id, personalized_content)
                    
                    # Отмечаем как отправленное
                    await cursor.execute("""
                        UPDATE smart_notifications 
                        SET is_sent = 1, sent_at = ?
                        WHERE id = ?
                    """, (current_time, notification_id))
                
                await conn.commit()
    
    async def _personalize_message(self, user_id: str, content: str, personalization: Dict[str, Any]) -> str:
        """Персонализация сообщения"""
        if user_id not in self.user_profiles:
            return content
        
        profile = self.user_profiles[user_id]
        
        # Добавляем персонализированные элементы
        personalized_content = content
        
        # Добавляем имя пользователя, если доступно
        if "user_name" in personalization:
            personalized_content = f"Привет, {personalization['user_name']}!\n\n{personalized_content}"
        
        # Добавляем информацию о сегменте
        if profile.segment == UserSegment.VIP_USER:
            personalized_content += "\n\n💎 Спасибо за лояльность! Вы наш VIP-клиент."
        elif profile.segment == UserSegment.TRIAL_USER:
            personalized_content += "\n\n🎁 Не забудьте воспользоваться пробным периодом!"
        
        # Добавляем информацию о рефералах
        if profile.referral_stats.get("total_referrals", 0) > 0:
            personalized_content += f"\n\n🤝 Вы привели {profile.referral_stats['total_referrals']} друзей!"
        
        return personalized_content
    
    async def _send_notification_to_user(self, user_id: str, content: str):
        """Отправка уведомления пользователю"""
        # Здесь должна быть логика отправки через бота
        logger.info(f"Sending personalized notification to user {user_id}: {content[:100]}...")
    
    async def _apply_personalization_rules(self):
        """Применение правил персонализации"""
        for rule_id, rule in self.personalization_rules.items():
            try:
                # Проверяем условия правила
                if await self._evaluate_rule_conditions(rule):
                    await self._execute_rule_actions(rule)
                    
                    # Обновляем счетчик срабатываний
                    async with aiosqlite.connect(self.db_path) as conn:
                        await conn.execute("""
                            UPDATE personalization_rules 
                            SET trigger_count = trigger_count + 1
                            WHERE id = ?
                        """, (rule_id,))
                        await conn.commit()
            
            except Exception as e:
                logger.error(f"Error applying personalization rule {rule_id}: {e}")
    
    async def _evaluate_rule_conditions(self, rule: Dict[str, Any]) -> bool:
        """Оценка условий правила"""
        # Здесь должна быть логика оценки условий
        # Пока возвращаем случайное значение для демонстрации
        return random.random() < 0.05  # 5% вероятность срабатывания
    
    async def _execute_rule_actions(self, rule: Dict[str, Any]):
        """Выполнение действий правила"""
        logger.info(f"Executing personalization rule: {rule['name']}")
        # Здесь должна быть логика выполнения действий
    
    async def get_personalization_stats(self) -> Dict[str, Any]:
        """Получение статистики персонализации"""
        return {
            "is_running": self.is_running,
            "total_profiles": len(self.user_profiles),
            "pending_notifications": len([n for n in self.smart_notifications if not n.is_sent]),
            "personalization_rules": len(self.personalization_rules),
            "user_segments": {
                segment.value: len([p for p in self.user_profiles.values() if p.segment == segment])
                for segment in UserSegment
            }
        }




