"""
Aggregates every module's router under /api/v1. main.py imports only this
file — adding a new module never requires touching main.py again.
"""
from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.version import router as version_router
from app.modules.auth.login.router import router as login_router
from app.modules.auth.me.router import router as me_router
from app.modules.auth.refresh.router import router as refresh_router
from app.modules.auth.registration.router import router as registration_router
from app.modules.auth.router import router as auth_router
from app.modules.permissions.router import router as permissions_router
from app.modules.roles.router import router as roles_router
from app.modules.subjects.router import router as subjects_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

# Foundation / infrastructure endpoints (not tied to a business module)
api_router.include_router(health_router)
api_router.include_router(version_router)

# Business modules
api_router.include_router(auth_router)
api_router.include_router(registration_router)  # isolated Sprint 3 Step 3 — see auth/registration/README.md
api_router.include_router(login_router)          # isolated Sprint 3 Step 4 — see auth/login/README.md
api_router.include_router(refresh_router)        # isolated Sprint 3 Step 5 — see auth/refresh/README.md
api_router.include_router(me_router)             # isolated Sprint 3 Step 6 — see auth/me/README.md
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(subjects_router)

# As modules are implemented, register them here, e.g.:
# from app.modules.grades.router import router as grades_router
# api_router.include_router(grades_router)
