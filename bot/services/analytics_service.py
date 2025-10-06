"""
Продвинутая аналитика и A/B тестирование для бота
"""
import asyncio
import logging
import time
import random
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import aiosqlite
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ExperimentStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class VariantType(Enum):
    TEXT = "text"
    KEYBOARD = "keyboard"
    IMAGE = "image"
    TIMING = "timing"

@dataclass
class ExperimentVariant:
    id: str
    name: str
    variant_type: VariantType
    content: Dict[str, Any]
    weight: float = 0.5  # Вес варианта (0.0 - 1.0)
    is_control: bool = False

@dataclass
class Experiment:
    id: str
    name: str
    description: str
    status: ExperimentStatus
    variants: List[ExperimentVariant]
    target_segment: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    created_at: float = 0
    metrics: Dict[str, Any] = None

@dataclass
class UserExperiment:
    user_id: str
    experiment_id: str
    variant_id: str
    assigned_at: float
    converted: bool = False
    conversion_time: Optional[float] = None

class AnalyticsService:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.active_experiments: Dict[str, Experiment] = {}
        self.user_assignments: Dict[str, Dict[str, str]] = {}  # user_id -> {experiment_id: variant_id}
        
    async def init_database(self):
        """Инициализация таблиц для аналитики"""
        async with aiosqlite.connect(self.db_path) as conn:
            # Таблица экспериментов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    target_segment TEXT NOT NULL,
                    start_time REAL,
                    end_time REAL,
                    created_at REAL NOT NULL,
                    metrics TEXT
                )
            """)
            
            # Таблица вариантов экспериментов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS experiment_variants (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    variant_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    weight REAL DEFAULT 0.5,
                    is_control INTEGER DEFAULT 0,
                    FOREIGN KEY (experiment_id) REFERENCES experiments (id)
                )
            """)
            
            # Таблица назначений пользователей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_experiments (
                    user_id TEXT,
                    experiment_id TEXT,
                    variant_id TEXT,
                    assigned_at REAL NOT NULL,
                    converted INTEGER DEFAULT 0,
                    conversion_time REAL,
                    PRIMARY KEY (user_id, experiment_id),
                    FOREIGN KEY (experiment_id) REFERENCES experiments (id),
                    FOREIGN KEY (variant_id) REFERENCES experiment_variants (id)
                )
            """)
            
            # Таблица событий для аналитики
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    timestamp REAL NOT NULL,
                    experiment_id TEXT,
                    variant_id TEXT
                )
            """)
            
            await conn.commit()

    async def create_experiment(
        self,
        name: str,
        description: str,
        target_segment: str,
        variants: List[Dict[str, Any]]
    ) -> str:
        """Создание нового A/B эксперимента"""
        experiment_id = f"exp_{int(time.time())}_{hash(name) % 10000}"
        
        # Создаем варианты
        experiment_variants = []
        for i, variant_data in enumerate(variants):
            variant_id = f"var_{experiment_id}_{i}"
            variant = ExperimentVariant(
                id=variant_id,
                name=variant_data["name"],
                variant_type=VariantType(variant_data["type"]),
                content=variant_data["content"],
                weight=variant_data.get("weight", 0.5),
                is_control=variant_data.get("is_control", i == 0)
            )
            experiment_variants.append(variant)
        
        experiment = Experiment(
            id=experiment_id,
            name=name,
            description=description,
            status=ExperimentStatus.DRAFT,
            variants=experiment_variants,
            target_segment=target_segment,
            created_at=time.time()
        )
        
        # Сохраняем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO experiments 
                (id, name, description, status, target_segment, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (experiment_id, name, description, ExperimentStatus.DRAFT.value, target_segment, time.time()))
            
            for variant in experiment_variants:
                await conn.execute("""
                    INSERT INTO experiment_variants 
                    (id, experiment_id, name, variant_type, content, weight, is_control)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    variant.id, experiment_id, variant.name, variant.variant_type.value,
                    json.dumps(variant.content), variant.weight, variant.is_control
                ))
            
            await conn.commit()
        
        self.active_experiments[experiment_id] = experiment
        return experiment_id

    async def start_experiment(self, experiment_id: str) -> bool:
        """Запуск эксперимента"""
        if experiment_id not in self.active_experiments:
            return False
        
        experiment = self.active_experiments[experiment_id]
        if experiment.status != ExperimentStatus.DRAFT:
            return False
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_time = time.time()
        
        # Обновляем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE experiments 
                SET status = ?, start_time = ?
                WHERE id = ?
            """, (ExperimentStatus.RUNNING.value, experiment.start_time, experiment_id))
            await conn.commit()
        
        return True

    async def assign_user_to_variant(self, user_id: str, experiment_id: str) -> Optional[str]:
        """Назначение пользователя к варианту эксперимента"""
        # Проверяем, не назначен ли уже пользователь
        if user_id in self.user_assignments and experiment_id in self.user_assignments[user_id]:
            return self.user_assignments[user_id][experiment_id]
        
        if experiment_id not in self.active_experiments:
            return None
        
        experiment = self.active_experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # Выбираем вариант на основе весов
        variant = self._select_variant(experiment.variants)
        
        # Сохраняем назначение
        if user_id not in self.user_assignments:
            self.user_assignments[user_id] = {}
        
        self.user_assignments[user_id][experiment_id] = variant.id
        
        # Сохраняем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO user_experiments 
                (user_id, experiment_id, variant_id, assigned_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, experiment_id, variant.id, time.time()))
            await conn.commit()
        
        return variant.id

    def _select_variant(self, variants: List[ExperimentVariant]) -> ExperimentVariant:
        """Выбор варианта на основе весов"""
        total_weight = sum(v.weight for v in variants)
        random_value = random.random() * total_weight
        
        current_weight = 0
        for variant in variants:
            current_weight += variant.weight
            if random_value <= current_weight:
                return variant
        
        # Fallback на первый вариант
        return variants[0]

    async def track_event(
        self,
        user_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[str] = None
    ):
        """Отслеживание события для аналитики"""
        event_id = f"event_{int(time.time())}_{hash(f'{user_id}_{event_type}') % 10000}"
        
        # Получаем вариант эксперимента, если применимо
        variant_id = None
        if experiment_id and user_id in self.user_assignments:
            variant_id = self.user_assignments[user_id].get(experiment_id)
        
        # Сохраняем событие
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO analytics_events 
                (id, user_id, event_type, event_data, timestamp, experiment_id, variant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, user_id, event_type,
                json.dumps(event_data) if event_data else None,
                time.time(), experiment_id, variant_id
            ))
            await conn.commit()

    async def mark_conversion(self, user_id: str, experiment_id: str) -> bool:
        """Отметка конверсии для пользователя в эксперименте"""
        if user_id not in self.user_assignments or experiment_id not in self.user_assignments[user_id]:
            return False
        
        variant_id = self.user_assignments[user_id][experiment_id]
        
        # Обновляем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE user_experiments 
                SET converted = 1, conversion_time = ?
                WHERE user_id = ? AND experiment_id = ?
            """, (time.time(), user_id, experiment_id))
            await conn.commit()
        
        return True

    async def get_experiment_results(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Получение результатов эксперимента"""
        if experiment_id not in self.active_experiments:
            return None
        
        experiment = self.active_experiments[experiment_id]
        
        # Получаем статистику по вариантам
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                results = {}
                
                for variant in experiment.variants:
                    # Общее количество пользователей в варианте
                    await cursor.execute("""
                        SELECT COUNT(*) FROM user_experiments 
                        WHERE experiment_id = ? AND variant_id = ?
                    """, (experiment_id, variant.id))
                    total_users = (await cursor.fetchone())[0]
                    
                    # Количество конверсий
                    await cursor.execute("""
                        SELECT COUNT(*) FROM user_experiments 
                        WHERE experiment_id = ? AND variant_id = ? AND converted = 1
                    """, (experiment_id, variant.id))
                    conversions = (await cursor.fetchone())[0]
                    
                    # Вычисляем конверсию
                    conversion_rate = (conversions / total_users * 100) if total_users > 0 else 0
                    
                    results[variant.id] = {
                        "name": variant.name,
                        "is_control": variant.is_control,
                        "total_users": total_users,
                        "conversions": conversions,
                        "conversion_rate": conversion_rate
                    }
                
                return {
                    "experiment_id": experiment_id,
                    "name": experiment.name,
                    "status": experiment.status.value,
                    "variants": results,
                    "total_users": sum(r["total_users"] for r in results.values()),
                    "total_conversions": sum(r["conversions"] for r in results.values())
                }

    async def get_user_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Получение аналитики по пользователю"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                # События пользователя
                await cursor.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM analytics_events 
                    WHERE user_id = ? AND timestamp > ?
                    GROUP BY event_type
                    ORDER BY count DESC
                """, (user_id, cutoff_time))
                events = await cursor.fetchall()
                
                # Эксперименты пользователя
                await cursor.execute("""
                    SELECT e.name, ev.name as variant_name, ue.converted, ue.assigned_at
                    FROM user_experiments ue
                    JOIN experiments e ON ue.experiment_id = e.id
                    JOIN experiment_variants ev ON ue.variant_id = ev.id
                    WHERE ue.user_id = ?
                """, (user_id,))
                experiments = await cursor.fetchall()
                
                return {
                    "user_id": user_id,
                    "period_days": days,
                    "events": {event_type: count for event_type, count in events},
                    "experiments": [
                        {
                            "experiment_name": exp_name,
                            "variant_name": var_name,
                            "converted": bool(converted),
                            "assigned_at": assigned_at
                        }
                        for exp_name, var_name, converted, assigned_at in experiments
                    ]
                }

    async def get_global_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Получение глобальной аналитики"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.cursor() as cursor:
                # Общая статистика событий
                await cursor.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM analytics_events 
                    WHERE timestamp > ?
                    GROUP BY event_type
                    ORDER BY count DESC
                """, (cutoff_time,))
                events = await cursor.fetchall()
                
                # Статистика экспериментов
                await cursor.execute("""
                    SELECT e.name, COUNT(DISTINCT ue.user_id) as users, 
                           SUM(ue.converted) as conversions
                    FROM experiments e
                    LEFT JOIN user_experiments ue ON e.id = ue.experiment_id
                    WHERE e.created_at > ?
                    GROUP BY e.id, e.name
                """, (cutoff_time,))
                experiments = await cursor.fetchall()
                
                # Активные пользователи
                await cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) 
                    FROM analytics_events 
                    WHERE timestamp > ?
                """, (cutoff_time,))
                active_users = (await cursor.fetchone())[0]
                
                return {
                    "period_days": days,
                    "active_users": active_users,
                    "events": {event_type: count for event_type, count in events},
                    "experiments": [
                        {
                            "name": name,
                            "users": users,
                            "conversions": conversions,
                            "conversion_rate": (conversions / users * 100) if users > 0 else 0
                        }
                        for name, users, conversions in experiments
                    ]
                }

    async def stop_experiment(self, experiment_id: str) -> bool:
        """Остановка эксперимента"""
        if experiment_id not in self.active_experiments:
            return False
        
        experiment = self.active_experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            return False
        
        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_time = time.time()
        
        # Обновляем в БД
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE experiments 
                SET status = ?, end_time = ?
                WHERE id = ?
            """, (ExperimentStatus.COMPLETED.value, experiment.end_time, experiment_id))
            await conn.commit()
        
        return True

    async def get_experiment_recommendations(self, experiment_id: str) -> List[str]:
        """Получение рекомендаций по эксперименту"""
        results = await self.get_experiment_results(experiment_id)
        if not results:
            return []
        
        recommendations = []
        variants = results["variants"]
        
        if len(variants) < 2:
            return ["Недостаточно данных для анализа"]
        
        # Находим контрольный вариант
        control_variant = None
        test_variants = []
        
        for variant_id, data in variants.items():
            if data["is_control"]:
                control_variant = data
            else:
                test_variants.append((variant_id, data))
        
        if not control_variant:
            return ["Контрольный вариант не найден"]
        
        # Анализируем результаты
        for variant_id, data in test_variants:
            if data["total_users"] < 100:
                recommendations.append(f"Вариант '{data['name']}' имеет недостаточно пользователей для статистической значимости")
                continue
            
            improvement = data["conversion_rate"] - control_variant["conversion_rate"]
            
            if improvement > 5:
                recommendations.append(f"✅ Вариант '{data['name']}' показывает значительное улучшение (+{improvement:.1f}%)")
            elif improvement > 0:
                recommendations.append(f"📈 Вариант '{data['name']}' показывает небольшое улучшение (+{improvement:.1f}%)")
            elif improvement < -5:
                recommendations.append(f"❌ Вариант '{data['name']}' показывает значительное ухудшение ({improvement:.1f}%)")
            else:
                recommendations.append(f"➡️ Вариант '{data['name']}' показывает нейтральные результаты ({improvement:+.1f}%)")
        
        return recommendations

