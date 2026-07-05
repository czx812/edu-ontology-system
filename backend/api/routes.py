from fastapi import APIRouter

from api.export import router as export_router
from api.generate import router as generate_router
from api.upload import router as upload_router


api_router = APIRouter()
api_router.include_router(upload_router)
api_router.include_router(generate_router)
api_router.include_router(export_router)
