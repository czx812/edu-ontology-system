from fastapi import APIRouter

from .auth import router as auth_router
from .export import router as export_router
from .generate import router as generate_router
from .upload import router as upload_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(upload_router)
api_router.include_router(generate_router)
api_router.include_router(export_router)