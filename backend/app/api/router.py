"""
Aggregates every module's router under /api/v1. main.py imports only this
file — adding a new module never requires touching main.py again.

Sprint 4 (Auth Cutover): the Sprint 3 isolated -v2 routers (registration,
login-v2, refresh-v2, me-v2) have been removed — their logic was merged
into the single `auth_router` below (backed by the unified core/security/
PasswordService + JWTService).
"""
from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.version import router as version_router
from app.modules.attempts.router import router as attempts_router
from app.modules.auth.router import router as auth_router
from app.modules.grades.router import router as grades_router
from app.modules.lessons.router import router as lessons_router
from app.modules.permissions.router import router as permissions_router
from app.modules.questions.router import router as questions_router
from app.modules.roles.router import router as roles_router
from app.modules.subjects.router import router as subjects_router
from app.modules.tests.router import router as tests_router
from app.modules.topics.router import router as topics_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

# Foundation / infrastructure endpoints (not tied to a business module)
api_router.include_router(health_router)
api_router.include_router(version_router)

# Business modules
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(subjects_router)
api_router.include_router(grades_router)
api_router.include_router(topics_router)
api_router.include_router(lessons_router)
api_router.include_router(tests_router)
api_router.include_router(questions_router)
api_router.include_router(attempts_router)

# As modules are implemented, register them here, e.g.:
# from app.modules.results.router import router as results_router
# api_router.include_router(results_router)
