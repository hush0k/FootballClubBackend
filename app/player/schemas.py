from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.player.models import LineUp, PlayerStatus, Position, Training


class PlayerBase(BaseModel):
    name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    nation: str = Field(max_length=100)
    age: int = Field(ge=9, le=60)  # воспитанникам академии от 9 лет
    salary: float = Field(ge=0)
    price: float = Field(ge=0)
    power: int = Field(ge=0, le=100)
    potential: int = Field(ge=0, le=100)
    img_url: str = Field(max_length=255)
    position: Position
    status: PlayerStatus
    number: int | None = Field(default=None, ge=1, le=99)
    line_up: LineUp | None = None
    training: Training | None = None  # не задана — умеренная для воспитанника, иначе без тренировок
    club: str | None = Field(default=None, max_length=100)
    league: str | None = Field(default=None, max_length=100)


class PlayerCreate(PlayerBase):
    # воспитаннику возраст (9–14) и сила (45–63) выпадают случайно — переданные значения игнорируются
    age: int | None = Field(default=None, ge=9, le=60)
    power: int | None = Field(default=None, ge=0, le=100)
    # не задан — выпадает случайно (чаще всего 80–87, 95+ примерно у 5%); воспитаннику всегда случайный
    potential: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _check_power(self):
        if self.line_up != LineUp.ACADEMY:
            if self.age is None or self.power is None:
                raise ValueError("age и power обязательны для всех, кроме воспитанников")
            if self.potential is not None and self.potential < self.power:
                raise ValueError("potential не может быть меньше power")
        return self


class PlayerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    nation: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=9, le=60)
    salary: float | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    power: int | None = Field(default=None, ge=0, le=100)
    potential: int | None = Field(default=None, ge=0, le=100)
    img_url: str | None = Field(default=None, max_length=255)
    position: Position | None = None
    number: int | None = Field(default=None, ge=1, le=99)
    line_up: LineUp | None = None
    training: Training | None = None
    club: str | None = Field(default=None, max_length=100)
    league: str | None = Field(default=None, max_length=100)


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    training: Training
    training_progress: int  # % накоплено в текущем цикле из 3 недель
    training_weeks: int  # сколько недель цикла уже прошло
    left_academy: bool  # уже переведён из академии — вернуть туда нельзя


# --- академия ---


class TrainingUpdate(BaseModel):
    training: Training


class AcademyRead(BaseModel):
    """Воспитанники и сколько веса тренировок занято (умеренная 1, обычная 2, интенсивная 3)."""

    weight_used: int
    weight_limit: int
    players: list[PlayerRead]


class TrainingResult(BaseModel):
    """Итог недели тренировок для одного воспитанника."""

    player_id: int
    training: Training
    week_progress: int  # % выпало на этой неделе
    training_progress: int  # % накоплено в цикле (после 3-й недели — 0)
    training_weeks: int
    power_gain: float  # 0 до конца цикла, на 3-й неделе — 1 × накопленный %
    power: int
    price: float  # растёт, когда сила проходит порог 70/75/80/85


class PlayerSale(BaseModel):
    """Итог продажи: price ушла в годовой бюджет, transfer_bonus — в трансферный (уже применено)."""

    player_id: int
    price: float
    transfer_bonus: float


# --- фильтры и сортировка списка игроков ---


class PositionGroup(StrEnum):
    GK = "gk"  # вратари
    DEF = "def"  # защита
    MID = "mid"  # полузащита
    ATT = "att"  # атака


class PlayerRank(StrEnum):
    WORLD_CLASS = "world_class"  # «Мировой класс», сила от 88
    STARTER = "starter"  # «Основа», 80–87
    RESERVE = "reserve"  # «Резерв», до 80


class PlayerSort(StrEnum):
    DEFAULT = "default"  # состав: статус → позиция → сила; маркет: по силе
    POWER = "power"  # сила, сильные выше
    PRICE = "price"  # стоимость, дорогие выше
    SALARY = "salary"  # зарплата, большие выше
    AGE = "age"  # возраст, молодые выше
    NUMBER = "number"  # номер по возрастанию
    NAME = "name"  # фамилия по алфавиту


class PlayerFilter(BaseModel):
    """Query-параметры GET /player. Списочные параметры повторяются: ?position=ЦЗ&position=ЛЗ."""

    model_config = ConfigDict(extra="forbid")

    status: PlayerStatus | None = None
    line_up: list[LineUp] = []
    position: list[Position] = []
    group: list[PositionGroup] = []
    rank: list[PlayerRank] = []
    club: list[str] = []
    league: list[str] = []
    nation: list[str] = []
    search: str | None = Field(default=None, max_length=100)  # имя, фамилия или клуб
    min_power: int | None = Field(default=None, ge=0, le=100)
    max_power: int | None = Field(default=None, ge=0, le=100)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    min_salary: float | None = Field(default=None, ge=0)
    max_salary: float | None = Field(default=None, ge=0)
    min_age: int | None = Field(default=None, ge=0)
    max_age: int | None = Field(default=None, ge=0)
    affordable: bool = False  # только те, кого клуб может купить прямо сейчас
    sort: PlayerSort = PlayerSort.DEFAULT
    reverse: bool = False  # «Обратный порядок»
    limit: int | None = Field(default=None, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class FilterOption(BaseModel):
    value: str
    count: int


class Range(BaseModel):
    min: float | None
    max: float | None


class PlayerFilterOptions(BaseModel):
    """Что можно выбрать в фильтрах (значения и сколько игроков под каждым) для выбранного статуса."""

    total: int
    line_up: list[FilterOption]
    position: list[FilterOption]
    group: list[FilterOption]
    rank: list[FilterOption]
    club: list[FilterOption]
    league: list[FilterOption]
    nation: list[FilterOption]
    power: Range
    price: Range
    salary: Range
    age: Range
    sort: list[PlayerSort]
