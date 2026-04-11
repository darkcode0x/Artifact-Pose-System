from fastapi import APIRouter

from app.api.routes import auth, devices, health, inspections, models, pose, workflows

router = APIRouter()
router.include_router(auth.router, tags=["auth"])
router.include_router(health.router, tags=["health"])
router.include_router(devices.router, tags=["devices"])
router.include_router(inspections.router, tags=["inspections"])
router.include_router(models.router, tags=["models"])
router.include_router(pose.router, tags=["pose"])
router.include_router(workflows.router, tags=["workflows"])
