from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.whatsapp import router as whatsapp_router
from api.routes.health import router as health_router
from api.routes.admin import router as admin_router
from core.logger import logger


def create_app() -> FastAPI:
    """Factory function untuk inisialisasi aplikasi FastAPI."""
    app = FastAPI(
        title="TaniPintar Bot API",
        description="WhatsApp AI Support Agent with RAG & Memory for Agriculture",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mendaftarkan Routers
    app.include_router(health_router)
    app.include_router(whatsapp_router)
    app.include_router(admin_router)

    @app.on_event("startup")
    async def startup_event():
        logger.info("🚀 TaniPintar Bot API berhasil dimulai dan siap melayani petani!")

    return app


app = create_app()
