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
from app.modules.ai.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.attempts.router import router as attempts_router
from app.modules.audit_logs.router import router as audit_logs_router
from app.modules.auth.router import router as auth_router
from app.modules.certificates.router import router as certificates_router
from app.modules.certificates.router import template_router as certificate_templates_router
from app.modules.grades.router import router as grades_router
from app.modules.learning_centers.router import router as learning_centers_router
from app.modules.lessons.router import router as lessons_router
from app.modules.notifications.router import router as notifications_router
from app.modules.payments.router import router as payments_router
from app.modules.permissions.router import router as permissions_router
from app.modules.profiles.router import router as profiles_router
from app.modules.questions.router import router as questions_router
from app.modules.results.router import router as results_router
from app.modules.roles.router import router as roles_router
from app.modules.schools.router import router as schools_router
from app.modules.settings.router import router as settings_router
from app.modules.subjects.router import router as subjects_router
from app.modules.system_logs.router import router as system_logs_router
from app.modules.tests.router import router as tests_router
from app.modules.topics.router import router as topics_router
from app.modules.uploads.router import router as uploads_router
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
api_router.include_router(results_router)
api_router.include_router(certificates_router)
api_router.include_router(certificate_templates_router)
api_router.include_router(analytics_router)
api_router.include_router(settings_router)
api_router.include_router(uploads_router)
api_router.include_router(notifications_router)
api_router.include_router(ai_router)
api_router.include_router(payments_router)
api_router.include_router(schools_router)
api_router.include_router(learning_centers_router)
api_router.include_router(profiles_router)
api_router.include_router(audit_logs_router)
api_router.include_router(system_logs_router)

# Sprint 12 complete. As modules are implemented, register them here.
