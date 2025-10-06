"""
Модуль мониторинга для админ-панели
"""
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = Router()

# Импортируем is_admin из main модуля
from .main import is_admin

# Глобальная переменная для сервиса мониторинга
monitoring_service = None

def init_monitoring_service(service):
    """Инициализация сервиса мониторинга"""
    global monitoring_service
    monitoring_service = service
    return monitoring_service

@router.callback_query(F.data == "admin_monitoring")
async def monitoring_dashboard(callback: types.CallbackQuery):
    """Дашборд мониторинга"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    if not monitoring_service:
        await callback.message.edit_text(
            "❌ <b>Мониторинг недоступен</b>\n\n"
            "Сервис мониторинга не инициализирован.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    try:
        # Получаем статус системы
        system_status = await monitoring_service.get_system_status()
        bot_metrics = await monitoring_service.get_bot_metrics()
        alerts = await monitoring_service.get_alerts()
        
        # Формируем статус
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️", 
            "critical": "🚨",
            "unknown": "❓"
        }
        
        status_emoji_str = status_emoji.get(system_status["status"], "❓")
        
        text = f"📊 <b>Мониторинг системы</b>\n\n"
        text += f"{status_emoji_str} <b>Статус:</b> {system_status['status'].upper()}\n"
        text += f"📝 <b>Сообщение:</b> {system_status['message']}\n\n"
        
        # Системные метрики
        if "system_metrics" in system_status:
            metrics = system_status["system_metrics"]
            text += f"💻 <b>Системные ресурсы:</b>\n"
            text += f"• CPU: {metrics['cpu_percent']:.1f}%\n"
            text += f"• RAM: {metrics['memory_percent']:.1f}% ({metrics['memory_used_mb']:.1f} MB)\n"
            text += f"• Диск: {metrics['disk_usage_percent']:.1f}%\n\n"
        
        # Метрики бота
        if bot_metrics.get("status") != "no_data":
            text += f"🤖 <b>Метрики бота:</b>\n"
            text += f"• Пользователей: {bot_metrics['total_users']}\n"
            text += f"• Активных (24ч): {bot_metrics['active_users_24h']}\n"
            text += f"• Новых сегодня: {bot_metrics['new_users_today']}\n"
            text += f"• Платежей сегодня: {bot_metrics['payments_today']}\n"
            text += f"• Доход сегодня: {bot_metrics['revenue_today']:.0f} ₽\n\n"
        
        # Алерты
        if alerts:
            text += f"🚨 <b>Активные алерты ({len(alerts)}):</b>\n"
            for alert in alerts[:3]:  # Показываем только первые 3
                emoji = "🚨" if alert["type"] == "critical" else "⚠️"
                text += f"{emoji} {alert['service']}: {alert['message'][:50]}...\n"
            if len(alerts) > 3:
                text += f"... и еще {len(alerts) - 3} алертов\n"
        else:
            text += "✅ <b>Активных алертов нет</b>\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_monitoring")],
            [InlineKeyboardButton(text="📈 Детальные метрики", callback_data="admin_detailed_metrics")],
            [InlineKeyboardButton(text="🚨 Алерты", callback_data="admin_alerts")],
            [InlineKeyboardButton(text="📊 История", callback_data="admin_metrics_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_panel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in monitoring dashboard: {e}")
        await callback.message.edit_text(f"❌ Ошибка получения метрик: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_detailed_metrics")
async def detailed_metrics(callback: types.CallbackQuery):
    """Детальные метрики"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        system_status = await monitoring_service.get_system_status()
        bot_metrics = await monitoring_service.get_bot_metrics()
        
        text = "📈 <b>Детальные метрики</b>\n\n"
        
        # Системные метрики
        if "system_metrics" in system_status:
            metrics = system_status["system_metrics"]
            text += f"💻 <b>Системные ресурсы:</b>\n"
            text += f"• CPU: {metrics['cpu_percent']:.2f}%\n"
            text += f"• RAM: {metrics['memory_percent']:.2f}% ({metrics['memory_used_mb']:.2f} MB)\n"
            text += f"• Диск: {metrics['disk_usage_percent']:.2f}%\n\n"
        
        # Health checks
        if "health_checks" in system_status:
            text += f"🔍 <b>Проверки состояния:</b>\n"
            for check in system_status["health_checks"]:
                status_emoji = {
                    "healthy": "✅",
                    "warning": "⚠️",
                    "critical": "🚨"
                }
                emoji = status_emoji.get(check["status"], "❓")
                text += f"{emoji} {check['service']}: {check['message']}\n"
                if check.get("response_time"):
                    text += f"   ⏱️ Время отклика: {check['response_time']:.3f}s\n"
            text += "\n"
        
        # Метрики бота
        if bot_metrics.get("status") != "no_data":
            text += f"🤖 <b>Метрики бота:</b>\n"
            text += f"• Всего пользователей: {bot_metrics['total_users']}\n"
            text += f"• Активных за 24ч: {bot_metrics['active_users_24h']}\n"
            text += f"• Активных за 7д: {bot_metrics['active_users_7d']}\n"
            text += f"• Новых сегодня: {bot_metrics['new_users_today']}\n"
            text += f"• Платежей сегодня: {bot_metrics['payments_today']}\n"
            text += f"• Доход сегодня: {bot_metrics['revenue_today']:.2f} ₽\n"
            text += f"• Рост пользователей: {bot_metrics.get('user_growth', 0)}\n"
            text += f"• Рост дохода: {bot_metrics.get('revenue_growth', 0):.2f} ₽\n"
            text += f"• Очередь рассылок: {bot_metrics['broadcast_queue_size']}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_monitoring")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in detailed metrics: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_alerts")
async def show_alerts(callback: types.CallbackQuery):
    """Показ алертов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        alerts = await monitoring_service.get_alerts()
        
        if not alerts:
            text = "✅ <b>Активные алерты</b>\n\nНет активных алертов. Все системы работают нормально."
        else:
            text = f"🚨 <b>Активные алерты ({len(alerts)})</b>\n\n"
            
            critical_alerts = [a for a in alerts if a["type"] == "critical"]
            warning_alerts = [a for a in alerts if a["type"] == "warning"]
            
            if critical_alerts:
                text += f"🚨 <b>Критические ({len(critical_alerts)}):</b>\n"
                for alert in critical_alerts:
                    timestamp = datetime.fromtimestamp(alert["timestamp"])
                    text += f"• {alert['service']}: {alert['message']}\n"
                    text += f"  ⏰ {timestamp.strftime('%H:%M:%S')}\n\n"
            
            if warning_alerts:
                text += f"⚠️ <b>Предупреждения ({len(warning_alerts)}):</b>\n"
                for alert in warning_alerts:
                    timestamp = datetime.fromtimestamp(alert["timestamp"])
                    text += f"• {alert['service']}: {alert['message']}\n"
                    text += f"  ⏰ {timestamp.strftime('%H:%M:%S')}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_alerts")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_monitoring")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing alerts: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "admin_metrics_history")
async def metrics_history(callback: types.CallbackQuery):
    """История метрик"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        # Получаем историю за последние 6 часов
        historical_data = await monitoring_service.get_historical_metrics(hours=6)
        
        text = "📊 <b>История метрик (6 часов)</b>\n\n"
        
        if historical_data["system_metrics"]:
            latest_system = historical_data["system_metrics"][-1]
            oldest_system = historical_data["system_metrics"][0]
            
            text += f"💻 <b>Системные ресурсы:</b>\n"
            text += f"• CPU: {oldest_system['cpu_percent']:.1f}% → {latest_system['cpu_percent']:.1f}%\n"
            text += f"• RAM: {oldest_system['memory_percent']:.1f}% → {latest_system['memory_percent']:.1f}%\n"
            text += f"• Диск: {oldest_system['disk_usage_percent']:.1f}% → {latest_system['disk_usage_percent']:.1f}%\n\n"
        
        if historical_data["bot_metrics"]:
            latest_bot = historical_data["bot_metrics"][-1]
            oldest_bot = historical_data["bot_metrics"][0]
            
            text += f"🤖 <b>Метрики бота:</b>\n"
            text += f"• Пользователей: {oldest_bot['total_users']} → {latest_bot['total_users']}\n"
            text += f"• Новых: {oldest_bot['new_users_today']} → {latest_bot['new_users_today']}\n"
            text += f"• Платежей: {oldest_bot['payments_today']} → {latest_bot['payments_today']}\n"
            text += f"• Доход: {oldest_bot['revenue_today']:.0f} → {latest_bot['revenue_today']:.0f} ₽\n\n"
        
        # Показываем тренды
        if len(historical_data["system_metrics"]) > 1:
            cpu_values = [m["cpu_percent"] for m in historical_data["system_metrics"]]
            memory_values = [m["memory_percent"] for m in historical_data["system_metrics"]]
            
            cpu_avg = sum(cpu_values) / len(cpu_values)
            memory_avg = sum(memory_values) / len(memory_values)
            
            text += f"📈 <b>Средние значения:</b>\n"
            text += f"• CPU: {cpu_avg:.1f}%\n"
            text += f"• RAM: {memory_avg:.1f}%\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_metrics_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_monitoring")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing metrics history: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

