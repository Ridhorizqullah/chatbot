import uvicorn
from core.config import settings
from core.logger import logger


def main():
    """Entry point untuk menjalankan TaniPintar Bot FastAPI server (WAHA & Meta)."""
    logger.info(f"Menjalankan TaniPintar Server pada http://{settings.app_host}:{settings.app_port}")
    uvicorn.run(
        "api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=(settings.app_env == "development")
    )


if __name__ == "__main__":
    main()
