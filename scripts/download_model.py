"""
scripts/download_model.py
Descarga el modelo GGUF para EduIA.
Solo se ejecuta una vez, en la instalación o primera puesta en marcha.
El modelo se guarda en runtime/models/ dentro de la app.
"""

import os
import sys
import urllib.request
from pathlib import Path


# ─────────────────────────────────────────────
# MODELOS DISPONIBLES
# ─────────────────────────────────────────────
# Ordenados por recomendación para centros educativos españoles

MODELS = {
    "1": {
        "name": "Qwen2.5-1.5B-Instruct Q4_K_M",
        "description": "Recomendado para PCs con 4GB RAM. Rápido y eficiente.",
        "ram": "~1.5 GB",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size_mb": 986,
    },
    "2": {
        "name": "Phi-3.5-mini Q4_K_M",
        "description": "Mejor calidad de razonamiento. Requiere 4GB RAM completos.",
        "ram": "~2.5 GB",
        "filename": "phi-3.5-mini-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
        "size_mb": 2390,
    },
    "3": {
        "name": "Gemma-2-2B Q4_K_M",
        "description": "Buenas explicaciones en español. Requiere 4GB RAM.",
        "ram": "~2 GB",
        "filename": "gemma-2-2b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "size_mb": 1600,
    },
    "4": {
        "name": "SmolLM2-1.7B Q4_K_M",
        "description": "El más ligero. Para PCs muy limitados.",
        "ram": "~1.2 GB",
        "filename": "smollm2-1.7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/bartowski/SmolLM2-1.7B-Instruct-GGUF/resolve/main/SmolLM2-1.7B-Instruct-Q4_K_M.gguf",
        "size_mb": 1050,
    },
}


def get_models_dir() -> Path:
    base = Path(__file__).parent.parent
    models_dir = base / "runtime" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def show_progress(block_num, block_size, total_size):
    """Barra de progreso simple."""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, downloaded * 100 / total_size)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total_size / (1024 * 1024)
        bar = "█" * int(percent / 2) + "░" * (50 - int(percent / 2))
        print(f"\r  [{bar}] {percent:.1f}% ({downloaded_mb:.0f}/{total_mb:.0f} MB)", end="", flush=True)


def download_model(model_info: dict, models_dir: Path) -> bool:
    """Descarga el modelo mostrando progreso."""
    dest_path = models_dir / model_info["filename"]
    
    if dest_path.exists():
        print(f"\n  ✅ El modelo ya existe en: {dest_path}")
        return True
    
    print(f"\n  Descargando: {model_info['name']}")
    print(f"  Tamaño aproximado: {model_info['size_mb']} MB")
    print(f"  Destino: {dest_path}")
    print()
    
    try:
        urllib.request.urlretrieve(model_info["url"], dest_path, show_progress)
        print(f"\n\n  ✅ Modelo descargado correctamente")
        
        # Crear symlink/copia como nombre estándar de EduIA
        eduia_model = models_dir / "eduia-model.gguf"
        if not eduia_model.exists():
            import shutil
            shutil.copy2(dest_path, eduia_model)
            print(f"  ✅ Configurado como modelo activo de EduIA")
        
        return True
        
    except Exception as e:
        print(f"\n  ❌ Error descargando: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def main():
    print()
    print("=" * 60)
    print("  EduIA — Configuración del Modelo de IA")
    print("=" * 60)
    print()
    print("  Selecciona el modelo según la RAM del PC donde se usará:")
    print()
    
    for key, model in MODELS.items():
        print(f"  [{key}] {model['name']}")
        print(f"      {model['description']}")
        print(f"      RAM necesaria: {model['ram']}")
        print()
    
    while True:
        choice = input("  Tu elección (1-4): ").strip()
        if choice in MODELS:
            break
        print("  Por favor elige una opción del 1 al 4")
    
    model = MODELS[choice]
    models_dir = get_models_dir()
    
    print()
    print(f"  Modelo elegido: {model['name']}")
    print()
    
    success = download_model(model, models_dir)
    
    if success:
        print()
        print("=" * 60)
        print("  ✅ ¡Listo! EduIA está configurado.")
        print()
        print("  Para arrancar el backend:")
        print("  python backend/main.py")
        print("=" * 60)
    else:
        print()
        print("  ❌ No se pudo descargar el modelo.")
        print("  Comprueba tu conexión a internet e inténtalo de nuevo.")
        sys.exit(1)


if __name__ == "__main__":
    main()
