from fastapi import APIRouter
from core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint untuk memverifikasi kesiapan server."""
    return {
        "status": "success",
        "message": "TaniPintar Bot API is running healthy.",
        "data": {
            "app_env": settings.app_env,
            "gemini_configured": bool(settings.gemini_api_key),
            "supabase_configured": bool(settings.supabase_url and settings.supabase_service_role_key),
            "meta_wa_configured": bool(settings.meta_wa_access_token)
        }
    }
