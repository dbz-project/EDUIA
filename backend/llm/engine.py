"""
backend/llm/engine.py
Motor LLM — parámetros optimizados por ChatGPT para TTFT máximo.
Objetivo: primera respuesta < 10s en CPU, 4GB RAM.
"""

import os
import logging
from pathlib import Path
from typing import Generator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    model_path: str = ""
    n_ctx: int = 2048           # ChatGPT: no subir, paga en TTFT
    n_threads: int = 0          # 0 = autodetectar (cpu_count - 1)
    n_batch: int = 256          # ChatGPT: 256, subir a 512 si aguanta
    n_gpu_layers: int = 0       # CPU only para compatibilidad máxima
    max_tokens: int = 100       # ChatGPT: 100 — respuestas cortas = menos latencia
    temperature: float = 0.4   # ChatGPT: 0.4 — más consistencia socrática
    top_p: float = 0.9
    repeat_penalty: float = 1.1 # ChatGPT: evita repeticiones tipo "Pregunta:\nPregunta:"
    verbose: bool = False


class LLMEngine:
    """
    Motor LLM local optimizado para TTFT.
    Carga el modelo UNA vez y lo mantiene en memoria.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._model = None
        self._model_loaded = False

        if not self.config.model_path:
            self.config.model_path = self._find_model()

        # Autodetectar hilos — recomendación ChatGPT
        if self.config.n_threads == 0:
            cpu = os.cpu_count() or 4
            self.config.n_threads = max(4, cpu - 1)
            logger.info(f"Hilos detectados: {self.config.n_threads}")

    def _find_model(self) -> str:
        base = Path(__file__).parent.parent.parent
        models_dir = base / "runtime" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        # Prioridad: modelo fine-tuned > cualquier .gguf
        for name in ["eduia-model.gguf"]:
            p = models_dir / name
            if p.exists():
                logger.info(f"Modelo: {p}")
                return str(p)

        gguf = list(models_dir.glob("*.gguf"))
        if gguf:
            logger.info(f"Modelo: {gguf[0]}")
            return str(gguf[0])

        logger.error("No se encontró modelo. Ejecuta: python scripts/download_model.py")
        return ""

    def load(self) -> bool:
        if self._model_loaded:
            return True
        if not self.config.model_path or not os.path.exists(self.config.model_path):
            logger.error(f"Modelo no encontrado: {self.config.model_path}")
            return False
        try:
            from llama_cpp import Llama
            logger.info(f"Cargando modelo ({self.config.n_threads} hilos, "
                       f"ctx={self.config.n_ctx}, batch={self.config.n_batch})...")
            self._model = Llama(
                model_path=self.config.model_path,
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
                n_batch=self.config.n_batch,
                n_gpu_layers=self.config.n_gpu_layers,
                verbose=self.config.verbose,
            )
            self._model_loaded = True
            logger.info("[OK] Modelo listo")
            return True
        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            return False

    def is_loaded(self) -> bool:
        return self._model_loaded

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[list] = None,
    ) -> str:
        if not self._model_loaded and not self.load():
            return "Error: modelo no disponible."

        messages = self._build_messages(system_prompt, user_message, conversation_history)
        try:
            resp = self._model.create_chat_completion(
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                repeat_penalty=self.config.repeat_penalty,
                stream=False,
            )
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error en chat: {e}")
            return "Ha ocurrido un error. Inténtalo de nuevo."

    def chat_stream(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[list] = None,
    ) -> Generator[str, None, None]:
        if not self._model_loaded and not self.load():
            yield "Error: modelo no disponible."
            return

        messages = self._build_messages(system_prompt, user_message, conversation_history)
        try:
            stream = self._model.create_chat_completion(
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                repeat_penalty=self.config.repeat_penalty,
                stream=True,
            )
            for chunk in stream:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta and delta["content"]:
                    yield delta["content"]
        except Exception as e:
            logger.error(f"Error en stream: {e}")
            yield "\n[Error en la generación]"

    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: Optional[list] = None,
    ) -> list:
        """
        Construye el contexto.
        ChatGPT advierte: el crecimiento del historial es el mayor
        riesgo para el TTFT — limitamos a 6 turnos recientes.
        """
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-6:])  # máx 6 turnos = 12 mensajes
        messages.append({"role": "user", "content": user_message})
        return messages

    def unload(self):
        if self._model:
            del self._model
            self._model = None
            self._model_loaded = False
            logger.info("Modelo descargado de memoria")

    def get_model_info(self) -> dict:
        return {
            "loaded": self._model_loaded,
            "model_path": self.config.model_path,
            "model_name": Path(self.config.model_path).name if self.config.model_path else "Ninguno",
            "n_ctx": self.config.n_ctx,
            "n_threads": self.config.n_threads,
            "n_batch": self.config.n_batch,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }


engine = LLMEngine()


# ── Cargador con timeout y fallback automático ──────────────────
# Patrón recomendado por ChatGPT

def get_engine():
    """
    Retorna el motor LLM real si carga en < 30s.
    Si falla, retorna FallbackEngine transparentemente.
    El alumno nunca nota la diferencia.
    """
    import threading
    from backend.llm.fallback import FallbackEngine

    result = {"engine": None, "error": None}

    def _load():
        try:
            e = LLMEngine()
            if e.load():
                result["engine"] = e
            else:
                result["error"] = "load() returned False"
        except Exception as ex:
            result["error"] = str(ex)

    t = threading.Thread(target=_load, daemon=True)
    t.start()
    t.join(timeout=30)

    if result["engine"]:
        logger.info("[OK] Motor LLM real activo")
        return result["engine"]

    logger.warning("[FALLBACK] Activando motor de emergencia. Razón: %s",
                   result["error"] or "timeout 30s")
    return FallbackEngine()
