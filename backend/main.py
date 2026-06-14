"""
backend/main.py
Punto de entrada del backend.
Incluye logs de arranque detallados (recomendación ChatGPT checklist final).
"""

import sys
import logging
import uvicorn

# ── Logging ────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("eduia")


def log_boot_info():
    """
    Logs de arranque detallados — recomendación ChatGPT.
    Permite encontrar el punto de fallo en menos de 30 segundos.
    """
    import os
    from pathlib import Path

    logger.info("=" * 50)
    logger.info("  EduIA Backend v0.1.0")
    logger.info("  100% local — sin internet")
    logger.info("=" * 50)

    # Verificación crítica de ChatGPT: sys.executable debe apuntar al venv
    logger.info(f"[BOOT] Python executable: {sys.executable}")

    # Verificar llama_cpp desde el venv correcto
    try:
        import llama_cpp
        logger.info(f"[BOOT] llama_cpp: {llama_cpp.__file__}")
    except ImportError:
        logger.warning("[BOOT] llama_cpp no encontrado — se usará fallback")

    # Verificar modelo
    base = Path(__file__).parent.parent
    models_dir = base / "runtime" / "models"
    gguf_files = list(models_dir.glob("*.gguf")) if models_dir.exists() else []
    if gguf_files:
        logger.info(f"[BOOT] Modelo encontrado: {gguf_files[0].name}")
    else:
        logger.warning("[BOOT] No se encontró modelo .gguf — se usará fallback")

    logger.info("[BOOT] Iniciando backend...")


if __name__ == "__main__":
    log_boot_info()

    from backend.api.routes import app
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info",
        access_log=False,
    )
