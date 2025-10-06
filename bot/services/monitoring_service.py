"""
Система мониторинга и метрик для бота
"""
import asyncio
import logging
import time
import psutil
import aiosqlite
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    timestamp: float

@dataclass
class BotMetrics:
    total_users: int
    active_users_24h: int
    active_users_7d: int
    new_users_today: int
    payments_today: int
    revenue_today: float
    broadcast_queue_size: int
    timestamp: float

@dataclass
class HealthCheck:
    service: str
    status: str  # "healthy", "warning", "critical"
    message: str
    timestamp: float
    response_time: Optional[float] = None

class MonitoringService:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.metrics_history: List[SystemMetrics] = []
        self.bot_metrics_history: List[BotMetrics] = []
        self.health_checks: List[HealthCheck] = []
        self.is_monitoring = False
        self.monitoring_interval = 60  # секунды
        
    async def start_monitoring(self):
        """Запуск мониторинга"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        asyncio.create_task(self._monitoring_loop())
        logger.info("Monitoring service started")
    
    async def stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_monitoring = False
        logger.info("Monitoring service stopped")
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        while self.is_monitoring:
            try:
                # Собираем системные метрики
                system_metrics = await self._collect_system_metrics()
                self.metrics_history.append(system_metrics)
                
                # Собираем метрики бота
                bot_metrics = await self._collect_bot_metrics()
                self.bot_metrics_history.append(bot_metrics)
                
                # Выполняем health checks
                await self._perform_health_checks()
                
                # Очищаем старые метрики (оставляем только последние 24 часа)
                await self._cleanup_old_metrics()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Сбор системных метрик"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                disk_usage_percent=disk.percent,
                timestamp=time.time()
            )
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(0, 0, 0, 0, time.time())
    
    async def _collect_bot_metrics(self) -> BotMetrics:
        """Сбор метрик бота"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.cursor() as cursor:
                    # Общее количество пользователей
                    await cursor.execute("SELECT COUNT(*) FROM users")
                    total_users = (await cursor.fetchone())[0]
                    
                    # Активные пользователи за 24 часа
                    day_ago = int(time.time()) - (24 * 60 * 60)
                    await cursor.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE last_payment_at > ? OR trial_3d_used = 1
                    """, (day_ago,))
                    active_users_24h = (await cursor.fetchone())[0]
                    
                    # Активные пользователи за 7 дней
                    week_ago = int(time.time()) - (7 * 24 * 60 * 60)
                    await cursor.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE last_payment_at > ? OR trial_3d_used = 1
                    """, (week_ago,))
                    active_users_7d = (await cursor.fetchone())[0]
                    
                    # Новые пользователи сегодня
                    today_start = int(time.time()) - (time.time() % 86400)
                    await cursor.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE created_at > ?
                    """, (today_start,))
                    new_users_today = (await cursor.fetchone())[0]
                    
                    # Платежи сегодня
                    await cursor.execute("""
                        SELECT COUNT(*) FROM users 
                        WHERE last_payment_at > ?
                    """, (today_start,))
                    payments_today = (await cursor.fetchone())[0]
                    
                    # Доход сегодня
                    await cursor.execute("""
                        SELECT total_rub FROM payments_agg WHERE id = 1
                    """)
                    result = await cursor.fetchone()
                    revenue_today = result[0] if result and result[0] else 0
                    
                    return BotMetrics(
                        total_users=total_users,
                        active_users_24h=active_users_24h,
                        active_users_7d=active_users_7d,
                        new_users_today=new_users_today,
                        payments_today=payments_today,
                        revenue_today=revenue_today,
                        broadcast_queue_size=0,  # Будет заполнено из сервиса рассылок
                        timestamp=time.time()
                    )
        except Exception as e:
            logger.error(f"Error collecting bot metrics: {e}")
            return BotMetrics(0, 0, 0, 0, 0, 0, 0, time.time())
    
    async def _perform_health_checks(self):
        """Выполнение health checks"""
        checks = [
            ("database", self._check_database),
            ("memory", self._check_memory),
            ("disk", self._check_disk),
            ("cpu", self._check_cpu)
        ]
        
        for service, check_func in checks:
            try:
                start_time = time.time()
                status, message = await check_func()
                response_time = time.time() - start_time
                
                health_check = HealthCheck(
                    service=service,
                    status=status,
                    message=message,
                    timestamp=time.time(),
                    response_time=response_time
                )
                
                self.health_checks.append(health_check)
                
            except Exception as e:
                health_check = HealthCheck(
                    service=service,
                    status="critical",
                    message=f"Health check failed: {str(e)}",
                    timestamp=time.time()
                )
                self.health_checks.append(health_check)
    
    async def _check_database(self) -> tuple[str, str]:
        """Проверка состояния базы данных"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()
            
            return "healthy", "Database connection successful"
        except Exception as e:
            return "critical", f"Database error: {str(e)}"
    
    async def _check_memory(self) -> tuple[str, str]:
        """Проверка использования памяти"""
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return "critical", f"Memory usage critical: {memory.percent}%"
            elif memory.percent > 80:
                return "warning", f"Memory usage high: {memory.percent}%"
            else:
                return "healthy", f"Memory usage normal: {memory.percent}%"
        except Exception as e:
            return "critical", f"Memory check failed: {str(e)}"
    
    async def _check_disk(self) -> tuple[str, str]:
        """Проверка использования диска"""
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 95:
                return "critical", f"Disk usage critical: {disk.percent}%"
            elif disk.percent > 85:
                return "warning", f"Disk usage high: {disk.percent}%"
            else:
                return "healthy", f"Disk usage normal: {disk.percent}%"
        except Exception as e:
            return "critical", f"Disk check failed: {str(e)}"
    
    async def _check_cpu(self) -> tuple[str, str]:
        """Проверка загрузки CPU"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                return "critical", f"CPU usage critical: {cpu_percent}%"
            elif cpu_percent > 80:
                return "warning", f"CPU usage high: {cpu_percent}%"
            else:
                return "healthy", f"CPU usage normal: {cpu_percent}%"
        except Exception as e:
            return "critical", f"CPU check failed: {str(e)}"
    
    async def _cleanup_old_metrics(self):
        """Очистка старых метрик"""
        cutoff_time = time.time() - (24 * 60 * 60)  # 24 часа назад
        
        # Очищаем системные метрики
        self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        # Очищаем метрики бота
        self.bot_metrics_history = [m for m in self.bot_metrics_history if m.timestamp > cutoff_time]
        
        # Очищаем health checks
        self.health_checks = [h for h in self.health_checks if h.timestamp > cutoff_time]
    
    async def get_system_status(self) -> Dict:
        """Получение текущего статуса системы"""
        if not self.metrics_history:
            return {"status": "unknown", "message": "No metrics available"}
        
        latest_metrics = self.metrics_history[-1]
        latest_health = [h for h in self.health_checks if h.timestamp > time.time() - 300]  # Последние 5 минут
        
        # Определяем общий статус
        critical_issues = [h for h in latest_health if h.status == "critical"]
        warning_issues = [h for h in latest_health if h.status == "warning"]
        
        if critical_issues:
            status = "critical"
            message = f"Critical issues: {len(critical_issues)}"
        elif warning_issues:
            status = "warning"
            message = f"Warning issues: {len(warning_issues)}"
        else:
            status = "healthy"
            message = "All systems operational"
        
        return {
            "status": status,
            "message": message,
            "timestamp": time.time(),
            "system_metrics": {
                "cpu_percent": latest_metrics.cpu_percent,
                "memory_percent": latest_metrics.memory_percent,
                "memory_used_mb": latest_metrics.memory_used_mb,
                "disk_usage_percent": latest_metrics.disk_usage_percent
            },
            "health_checks": [
                {
                    "service": h.service,
                    "status": h.status,
                    "message": h.message,
                    "response_time": h.response_time
                }
                for h in latest_health
            ]
        }
    
    async def get_bot_metrics(self) -> Dict:
        """Получение метрик бота"""
        if not self.bot_metrics_history:
            return {"status": "no_data", "message": "No bot metrics available"}
        
        latest_metrics = self.bot_metrics_history[-1]
        
        # Вычисляем тренды
        if len(self.bot_metrics_history) >= 2:
            prev_metrics = self.bot_metrics_history[-2]
            user_growth = latest_metrics.total_users - prev_metrics.total_users
            revenue_growth = latest_metrics.revenue_today - prev_metrics.revenue_today
        else:
            user_growth = 0
            revenue_growth = 0
        
        return {
            "timestamp": latest_metrics.timestamp,
            "total_users": latest_metrics.total_users,
            "active_users_24h": latest_metrics.active_users_24h,
            "active_users_7d": latest_metrics.active_users_7d,
            "new_users_today": latest_metrics.new_users_today,
            "payments_today": latest_metrics.payments_today,
            "revenue_today": latest_metrics.revenue_today,
            "user_growth": user_growth,
            "revenue_growth": revenue_growth,
            "broadcast_queue_size": latest_metrics.broadcast_queue_size
        }
    
    async def get_historical_metrics(self, hours: int = 24) -> Dict:
        """Получение исторических метрик"""
        cutoff_time = time.time() - (hours * 60 * 60)
        
        system_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        bot_metrics = [m for m in self.bot_metrics_history if m.timestamp > cutoff_time]
        
        return {
            "system_metrics": [
                {
                    "timestamp": m.timestamp,
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "memory_used_mb": m.memory_used_mb,
                    "disk_usage_percent": m.disk_usage_percent
                }
                for m in system_metrics
            ],
            "bot_metrics": [
                {
                    "timestamp": m.timestamp,
                    "total_users": m.total_users,
                    "active_users_24h": m.active_users_24h,
                    "new_users_today": m.new_users_today,
                    "payments_today": m.payments_today,
                    "revenue_today": m.revenue_today
                }
                for m in bot_metrics
            ]
        }
    
    async def get_alerts(self) -> List[Dict]:
        """Получение активных алертов"""
        alerts = []
        current_time = time.time()
        
        # Проверяем критические health checks
        critical_checks = [h for h in self.health_checks if h.status == "critical" and h.timestamp > current_time - 3600]
        for check in critical_checks:
            alerts.append({
                "type": "critical",
                "service": check.service,
                "message": check.message,
                "timestamp": check.timestamp
            })
        
        # Проверяем предупреждения
        warning_checks = [h for h in self.health_checks if h.status == "warning" and h.timestamp > current_time - 3600]
        for check in warning_checks:
            alerts.append({
                "type": "warning",
                "service": check.service,
                "message": check.message,
                "timestamp": check.timestamp
            })
        
        return alerts

