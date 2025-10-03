# Пустой файл для создания пакета

# Импортируем функцию is_admin из main модуля
try:
    from .main import is_admin
    __all__ = ['is_admin']
except ImportError:
    # Если импорт не удался, создаем заглушку
    def is_admin(user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором."""
        return user_id == 746560409
    
    __all__ = ['is_admin']
