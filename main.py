"""
backend/main.py
Punto de entrada del backend local de EduIA.
Arranca FastAPI en localhost:8765 — nunca accesible desde fuera.
"""

import sys
import logging
import uvicorn
from backend.api.routes import app

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("eduia")


# ─────────────────────────────────────────────
# ARRANQUE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("  EduIA Backend v0.1.0")
    logger.info("  100% local — sin internet")
    logger.info("=" * 50)
    
    uvicorn.run(
        app,
        host="127.0.0.1",   # Solo localhost — NUNCA "0.0.0.0"
        port=8765,
        log_level="info",
        access_log=False,    # Sin logs de acceso para mayor privacidad
    )
