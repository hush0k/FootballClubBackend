import re

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import decode_access_token
from app.core.database import get_db
from app.player.models import Player, PlayerStatus

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


# Публичные (без токена) только безопасные GET-запросы на общие данные игры:
# турнирные таблицы, плей-офф, список клубов и трансферный рынок.
# Всё, чего нет в этом списке, по-прежнему требует токен.
PUBLIC_GET_PATHS = {
    "/team",
    "/season/standings",
    "/season/schedule",
    "/league-of-champions/standings",
    "/league-of-champions/playoff",
}
_PLAYER_ID_PATH = re.compile(r"^/player/(\d+)$")


async def is_public_request(request: Request, db: AsyncSession) -> bool:
    if request.method != "GET":
        return False
    path = request.url.path.rstrip("/") or "/"
    if path in PUBLIC_GET_PATHS:
        return True
    # Игроки: публично только маркет, состав клуба остаётся закрытым
    if path in ("/player", "/player/filters"):
        return request.query_params.get("status") == PlayerStatus.MARKET.value
    match = _PLAYER_ID_PATH.match(path)
    if match:
        player = await db.get(Player, int(match.group(1)))
        return player is not None and player.status == PlayerStatus.MARKET
    return False


async def get_current_user_or_public(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Пускает без токена только запросы из белого списка, остальным нужен токен."""
    if await is_public_request(request, db):
        return None
    return await get_current_user(credentials, db)
