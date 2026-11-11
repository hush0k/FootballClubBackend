from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import get_current_user
from app.auth.router import router as auth_router
from app.coach.router import router as coach_router
from app.core.config import settings
from app.core.database import engine
from app.finance.router import router as finance_router
from app.game.router import router as game_router
from app.game_engine.router import router as game_engine_router
from app.laliga.router import router as laliga_router
from app.league_of_champions.router import router as league_of_champions_router
from app.objective.router import router as objective_router
from app.player.router import router as player_router
from app.season.router import router as season_router
from app.stadium.router import router as stadium_router
from app.team.router import router as team_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    team_router,
    laliga_router,
    player_router,
    coach_router,
    stadium_router,
    game_engine_router,
    season_router,
    league_of_champions_router,
    finance_router,
    objective_router,
    game_router,
):
    # Все игровые эндпоинты доступны только авторизованным пользователям
    app.include_router(r, dependencies=[Depends(get_current_user)])

# /auth/register и /auth/login публичные, /auth/me защищён внутри роутера
app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
