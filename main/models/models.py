from pydantic import BaseModel


class CreateData(BaseModel):
    """Данные для создания конфигураций.

    Attributes
    ----------
    count : int
        Сколько новых конфигов создать (по умолчанию ``1``).
    server : str
        Код страны сервера (fi, nl, ...).
    """

    count: int = 1
    server: str


class ExtendConfig(BaseModel):
    """Данные для продления срока действия конфига."""

    time: int  # количество суток, на которое нужно продлить
    uid: str  # id продлеваемого конфига
    server: str  # код страны сервера


class ClientData(BaseModel):
    """Данные для активации (выдачи) конфигурации пользователю."""

    time: int  # срок действия в днях
    id: str  # telegram id пользователя
    server: str  # код страны сервера


class DeleteConfig(BaseModel):
    """Данные для удаления конфига."""

    uid: str  # id конфигурации для удаления
    server: str  # код страны сервера
