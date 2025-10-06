"""
Продвинутая система рассылок для админ-панели
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from services.broadcast_service import BroadcastService, BroadcastStatus

logger = logging.getLogger(__name__)
router = Router()

class AdvancedBroadcastStates(StatesGroup):
    waiting_for_campaign_name = State()
    waiting_for_campaign_text = State()
    waiting_for_segment_selection = State()
    waiting_for_parse_mode = State()
    waiting_for_reply_markup = State()

# Импортируем is_admin из main модуля
from .main import is_admin

# Глобальная переменная для сервиса рассылок
broadcast_service: BroadcastService = None

def init_broadcast_service(bot):
    """Инициализация сервиса рассылок"""
    global broadcast_service
    broadcast_service = BroadcastService(bot)
    return broadcast_service

@router.callback_query(F.data == "admin_advanced_broadcast")
async def advanced_broadcast_menu(callback: types.CallbackQuery):
    """Меню продвинутой системы рассылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать кампанию", callback_data="create_campaign")],
        [InlineKeyboardButton(text="📊 Активные кампании", callback_data="active_campaigns")],
        [InlineKeyboardButton(text="📈 Статистика кампаний", callback_data="campaign_stats")],
        [InlineKeyboardButton(text="🎯 Сегментация пользователей", callback_data="user_segments")],
        [InlineKeyboardButton(text="⚙️ Настройки рассылок", callback_data="broadcast_settings")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_panel")]
    ])
    
    await callback.message.edit_text(
        "📢 <b>Продвинутая система рассылок</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "create_campaign")
async def create_campaign_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания кампании"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 <b>Создание кампании рассылки</b>\n\n"
        "Введите название кампании:",
        parse_mode="HTML"
    )
    await state.set_state(AdvancedBroadcastStates.waiting_for_campaign_name)
    await callback.answer()

@router.message(AdvancedBroadcastStates.waiting_for_campaign_name)
async def process_campaign_name(message: types.Message, state: FSMContext):
    """Обработка названия кампании"""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    campaign_name = message.text.strip()
    if not campaign_name:
        await message.answer("Название кампании не может быть пустым. Попробуйте снова:")
        return
    
    await state.update_data(campaign_name=campaign_name)
    await message.answer(
        "📝 <b>Создание кампании рассылки</b>\n\n"
        f"Название: <b>{campaign_name}</b>\n\n"
        "Введите текст сообщения для рассылки:",
        parse_mode="HTML"
    )
    await state.set_state(AdvancedBroadcastStates.waiting_for_campaign_text)

@router.message(AdvancedBroadcastStates.waiting_for_campaign_text)
async def process_campaign_text(message: types.Message, state: FSMContext):
    """Обработка текста кампании"""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    campaign_text = message.text.strip()
    if not campaign_text:
        await message.answer("Текст сообщения не может быть пустым. Попробуйте снова:")
        return
    
    await state.update_data(campaign_text=campaign_text)
    
    # Показываем сегменты для выбора
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="segment_all")],
        [InlineKeyboardButton(text="✅ Активные подписчики", callback_data="segment_active")],
        [InlineKeyboardButton(text="🧪 Только пробная подписка", callback_data="segment_trial_only")],
        [InlineKeyboardButton(text="⏰ Истекшие подписки", callback_data="segment_expired")],
        [InlineKeyboardButton(text="❌ Без подписки", callback_data="segment_no_subscription")],
        [InlineKeyboardButton(text="🤝 С рефералами", callback_data="segment_with_referrals")],
        [InlineKeyboardButton(text="💎 VIP пользователи", callback_data="segment_vip")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_advanced_broadcast")]
    ])
    
    await message.answer(
        "📝 <b>Создание кампании рассылки</b>\n\n"
        f"Название: <b>{message.text[:50]}{'...' if len(message.text) > 50 else ''}</b>\n\n"
        "Выберите сегмент пользователей для рассылки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("segment_"))
async def process_segment_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора сегмента"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    segment = callback.data.replace("segment_", "")
    segment_names = {
        "all": "Все пользователи",
        "active": "Активные подписчики", 
        "trial_only": "Только пробная подписка",
        "expired": "Истекшие подписки",
        "no_subscription": "Без подписки",
        "with_referrals": "С рефералами",
        "vip": "VIP пользователи"
    }
    
    await state.update_data(target_segment=segment)
    
    # Показываем настройки форматирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Обычный текст", callback_data="parse_mode_none")],
        [InlineKeyboardButton(text="🔤 Markdown", callback_data="parse_mode_markdown")],
        [InlineKeyboardButton(text="📄 HTML", callback_data="parse_mode_html")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="create_campaign")]
    ])
    
    await callback.message.edit_text(
        "📝 <b>Создание кампании рассылки</b>\n\n"
        f"Сегмент: <b>{segment_names.get(segment, segment)}</b>\n\n"
        "Выберите режим форматирования текста:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("parse_mode_"))
async def process_parse_mode(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора режима форматирования"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    parse_mode = callback.data.replace("parse_mode_", "")
    if parse_mode == "none":
        parse_mode = None
    
    await state.update_data(parse_mode=parse_mode)
    
    # Создаем кампанию
    user_data = await state.get_data()
    
    try:
        campaign_id = await broadcast_service.create_campaign(
            name=user_data["campaign_name"],
            text=user_data["campaign_text"],
            target_segment=user_data["target_segment"],
            parse_mode=parse_mode
        )
        
        # Получаем количество пользователей в сегменте
        user_ids = await broadcast_service.get_users_by_segment(user_data["target_segment"])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить кампанию", callback_data=f"start_campaign_{campaign_id}")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_campaign_{campaign_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_campaign_{campaign_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_advanced_broadcast")]
        ])
        
        await callback.message.edit_text(
            "✅ <b>Кампания создана!</b>\n\n"
            f"📝 Название: <b>{user_data['campaign_name']}</b>\n"
            f"👥 Сегмент: <b>{user_data['target_segment']}</b>\n"
            f"📊 Пользователей: <b>{len(user_ids)}</b>\n"
            f"📝 Формат: <b>{parse_mode or 'Обычный текст'}</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при создании кампании: {str(e)}"
        )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("start_campaign_"))
async def start_campaign(callback: types.CallbackQuery):
    """Запуск кампании"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    campaign_id = callback.data.replace("start_campaign_", "")
    
    try:
        success = await broadcast_service.start_campaign(campaign_id)
        if success:
            await callback.message.edit_text(
                "🚀 <b>Кампания запущена!</b>\n\n"
                "Рассылка началась. Вы можете отслеживать прогресс в разделе 'Активные кампании'.",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка запуска кампании</b>\n\n"
                "Не удалось запустить кампанию. Проверьте настройки.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error starting campaign: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при запуске кампании: {str(e)}"
        )
    
    await callback.answer()

@router.callback_query(F.data == "active_campaigns")
async def show_active_campaigns(callback: types.CallbackQuery):
    """Показ активных кампаний"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        campaigns = []
        for campaign_id, campaign in broadcast_service.active_campaigns.items():
            if campaign.status == BroadcastStatus.SENDING:
                stats = await broadcast_service.get_campaign_stats(campaign_id)
                campaigns.append(stats)
        
        if not campaigns:
            await callback.message.edit_text(
                "📊 <b>Активные кампании</b>\n\n"
                "Нет активных кампаний.",
                parse_mode="HTML"
            )
            return
        
        text = "📊 <b>Активные кампании</b>\n\n"
        keyboard_buttons = []
        
        for campaign in campaigns:
            progress = campaign["progress"]
            text += (
                f"📝 <b>{campaign['name']}</b>\n"
                f"📊 Прогресс: {progress:.1f}%\n"
                f"✅ Отправлено: {campaign['sent_count']}\n"
                f"❌ Ошибок: {campaign['failed_count']}\n"
                f"🚫 Заблокировано: {campaign['blocked_count']}\n\n"
            )
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"⏹️ Остановить {campaign['name'][:20]}", 
                    callback_data=f"stop_campaign_{campaign['id']}"
                )
            ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_advanced_broadcast")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing active campaigns: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("stop_campaign_"))
async def stop_campaign(callback: types.CallbackQuery):
    """Остановка кампании"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    campaign_id = callback.data.replace("stop_campaign_", "")
    
    try:
        success = await broadcast_service.stop_campaign(campaign_id)
        if success:
            await callback.message.edit_text(
                "⏹️ <b>Кампания остановлена</b>\n\n"
                "Рассылка была прервана.",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка остановки кампании</b>\n\n"
                "Не удалось остановить кампанию.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error stopping campaign: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "campaign_stats")
async def show_campaign_stats(callback: types.CallbackQuery):
    """Показ статистики кампаний"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        # Получаем статистику из БД
        import aiosqlite
        async with aiosqlite.connect("users.db") as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT name, status, total_users, sent_count, failed_count, blocked_count, 
                           created_at, started_at, completed_at
                    FROM broadcast_campaigns 
                    ORDER BY created_at DESC 
                    LIMIT 10
                """)
                campaigns = await cursor.fetchall()
        
        if not campaigns:
            await callback.message.edit_text(
                "📈 <b>Статистика кампаний</b>\n\n"
                "Нет созданных кампаний.",
                parse_mode="HTML"
            )
            return
        
        text = "📈 <b>Статистика кампаний</b>\n\n"
        
        for campaign in campaigns:
            name, status, total, sent, failed, blocked, created, started, completed = campaign
            
            # Вычисляем конверсию
            conversion = (sent / total * 100) if total > 0 else 0
            
            # Время выполнения
            duration = ""
            if started and completed:
                duration = f"{(completed - started) / 60:.1f} мин"
            elif started:
                duration = "В процессе"
            
            text += (
                f"📝 <b>{name}</b>\n"
                f"📊 Статус: {status}\n"
                f"👥 Пользователей: {total}\n"
                f"✅ Отправлено: {sent} ({conversion:.1f}%)\n"
                f"❌ Ошибок: {failed}\n"
                f"🚫 Заблокировано: {blocked}\n"
                f"⏱️ Время: {duration}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_advanced_broadcast")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing campaign stats: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "user_segments")
async def show_user_segments(callback: types.CallbackQuery):
    """Показ сегментации пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    try:
        segments = {
            "all": "Все пользователи",
            "active": "Активные подписчики",
            "trial_only": "Только пробная подписка", 
            "expired": "Истекшие подписки",
            "no_subscription": "Без подписки",
            "with_referrals": "С рефералами",
            "vip": "VIP пользователи"
        }
        
        text = "🎯 <b>Сегментация пользователей</b>\n\n"
        
        for segment_key, segment_name in segments.items():
            user_ids = await broadcast_service.get_users_by_segment(segment_key)
            text += f"👥 <b>{segment_name}</b>: {len(user_ids)} пользователей\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_advanced_broadcast")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing user segments: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@router.callback_query(F.data == "broadcast_settings")
async def show_broadcast_settings(callback: types.CallbackQuery):
    """Настройки системы рассылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    text = (
        "⚙️ <b>Настройки системы рассылок</b>\n\n"
        f"📦 Размер батча: {broadcast_service.batch_size} сообщений\n"
        f"⏱️ Задержка между батчами: {broadcast_service.delay_between_batches} сек\n"
        f"🔄 Максимум попыток: {broadcast_service.max_retries}\n"
        f"⏳ Задержка между попытками: {broadcast_service.retry_delay} сек\n"
        f"🔄 Статус обработки: {'Активна' if broadcast_service.is_running else 'Остановлена'}\n\n"
        "Эти настройки можно изменить в коде сервиса рассылок."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_advanced_broadcast")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

