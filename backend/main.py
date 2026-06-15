"""
backend/main.py — Fix encoding Windows cp1252
Tauri lanza el proceso sin UTF-8, lo que rompe los emojis en logs.
"""

import sys
import os
import logging

# Fix crítico: forzar UTF-8 en stdout/stderr cuando lo lanza Tauri
# Sin esto los caracteres ✅ rompen el proceso en Windows cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# Alternativa más robusta: usar variable de entorno
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("eduia")


def log_boot_info():
    import os as _os
    from pathlib import Path

    logger.info("=" * 50)
    logger.info("  EduIA Backend v0.1.0")
    logger.info("  100% local - sin internet")
    logger.info("=" * 50)
    logger.info(f"[BOOT] Python executable: {sys.executable}")

    try:
        import llama_cpp
        logger.info(f"[BOOT] llama_cpp: {llama_cpp.__file__}")
    except ImportError:
        logger.warning("[BOOT] llama_cpp no encontrado - se usara fallback")

    base = Path(__file__).parent.parent
    models_dir = base / "runtime" / "models"
    gguf_files = list(models_dir.glob("*.gguf")) if models_dir.exists() else []
    if gguf_files:
        logger.info(f"[BOOT] Modelo encontrado: {gguf_files[0].name}")
    else:
        logger.warning("[BOOT] No se encontro modelo .gguf - se usara fallback")

    logger.info("[BOOT] Iniciando backend...")


if __name__ == "__main__":
    log_boot_info()

    import uvicorn
    from backend.api.routes import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info",
        access_log=False,
    )
