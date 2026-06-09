"""
backend/llm/engine.py
Motor LLM local — Wrapper sobre llama-cpp-python
Sin dependencias externas, sin internet, 100% local.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Generator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuración del modelo. Ajustada para PCs de 4GB RAM."""
    
    # Ruta al modelo .gguf
    model_path: str = ""
    
    # Contexto: 2048 es suficiente para conversación educativa y cabe en 4GB
    n_ctx: int = 2048
    
    # Hilos de CPU — se autodetecta, pero limitamos para no bloquear el PC
    n_threads: int = 4
    
    # GPU layers: 0 = solo CPU (para compatibilidad máxima en centros)
    # Subir a 20-35 si el PC tiene GPU NVIDIA
    n_gpu_layers: int = 0
    
    # Tokens máximos por respuesta
    max_tokens: int = 512
    
    # Temperatura: 0.7 es creativo pero consistente para educación
    temperature: float = 0.7
    
    # Top-p sampling
    top_p: float = 0.9
    
    # Repetition penalty — importante para que no se repita en tutorías
    repeat_penalty: float = 1.1
    
    # Verbose: False en producción para no llenar la consola
    verbose: bool = False


class LLMEngine:
    """
    Motor de IA local. 
    Carga el modelo una vez y lo mantiene en memoria.
    Soporta generación en streaming para UX fluida.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._model = None
        self._model_loaded = False
        
        # Detectar ruta del modelo automáticamente
        if not self.config.model_path:
            self.config.model_path = self._find_model()
    
    def _find_model(self) -> str:
        """
        Busca el modelo .gguf en la carpeta runtime/models.
        Primero busca el fine-tuned, luego cualquier .gguf disponible.
        """
        # Ruta relativa desde backend/llm/ hasta runtime/models/
        base = Path(__file__).parent.parent.parent
        models_dir = base / "runtime" / "models"
        
        if not models_dir.exists():
            models_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Carpeta de modelos creada en {models_dir}")
            logger.warning("Ejecuta: python scripts/download_model.py")
            return ""
        
        # Prioridad 1: modelo fine-tuned de EduIA
        eduia_model = models_dir / "eduia-model.gguf"
        if eduia_model.exists():
            logger.info(f"Modelo EduIA encontrado: {eduia_model}")
            return str(eduia_model)
        
        # Prioridad 2: cualquier .gguf en la carpeta
        gguf_files = list(models_dir.glob("*.gguf"))
        if gguf_files:
            model_path = str(gguf_files[0])
            logger.info(f"Modelo encontrado: {model_path}")
            return model_path
        
        logger.error("No se encontró ningún modelo .gguf en runtime/models/")
        return ""
    
    def load(self) -> bool:
        """
        Carga el modelo en memoria.
        Llama a esto al arrancar la app, no en cada petición.
        Retorna True si cargó correctamente.
        """
        if self._model_loaded:
            return True
        
        if not self.config.model_path or not os.path.exists(self.config.model_path):
            logger.error(f"Modelo no encontrado en: {self.config.model_path}")
            logger.error("Ejecuta primero: python scripts/download_model.py")
            return False
        
        try:
            from llama_cpp import Llama
            
            logger.info(f"Cargando modelo: {self.config.model_path}")
            logger.info(f"Configuración: ctx={self.config.n_ctx}, threads={self.config.n_threads}")
            
            self._model = Llama(
                model_path=self.config.model_path,
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
                n_gpu_layers=self.config.n_gpu_layers,
                verbose=self.config.verbose,
            )
            
            self._model_loaded = True
            logger.info("✅ Modelo cargado correctamente")
            return True
            
        except ImportError:
            logger.error("llama-cpp-python no está instalado.")
            logger.error("Ejecuta: pip install llama-cpp-python")
            return False
        except Exception as e:
            logger.error(f"Error al cargar el modelo: {e}")
            return False
    
    def is_loaded(self) -> bool:
        return self._model_loaded
    
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[list] = None,
    ) -> str:
        """
        Genera una respuesta completa (no streaming).
        Usa el formato ChatML estándar compatible con la mayoría de modelos.
        """
        if not self._model_loaded:
            if not self.load():
                return "Error: El modelo no está disponible."
        
        messages = self._build_messages(system_prompt, user_message, conversation_history)
        
        try:
            response = self._model.create_chat_completion(
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                repeat_penalty=self.config.repeat_penalty,
                stream=False,
            )
            return response["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return "Ha ocurrido un error. Por favor, inténtalo de nuevo."
    
    def chat_stream(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[list] = None,
    ) -> Generator[str, None, None]:
        """
        Genera respuesta en streaming (token a token).
        Usar esto en la API para UX fluida — el texto aparece mientras se genera.
        """
        if not self._model_loaded:
            if not self.load():
                yield "Error: El modelo no está disponible."
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
            logger.error(f"Error en streaming: {e}")
            yield "\n[Error en la generación]"
    
    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: Optional[list] = None,
    ) -> list:
        """
        Construye la lista de mensajes en formato ChatML.
        history = lista de {"role": "user"|"assistant", "content": "..."}
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            # Limitar historial a los últimos 10 turnos para no saturar el contexto
            recent_history = history[-10:]
            messages.extend(recent_history)
        
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def unload(self):
        """Libera el modelo de memoria."""
        if self._model:
            del self._model
            self._model = None
            self._model_loaded = False
            logger.info("Modelo descargado de memoria")
    
    def get_model_info(self) -> dict:
        """Info del modelo para mostrar en la UI."""
        return {
            "loaded": self._model_loaded,
            "model_path": self.config.model_path,
            "model_name": Path(self.config.model_path).name if self.config.model_path else "Ninguno",
            "n_ctx": self.config.n_ctx,
            "n_threads": self.config.n_threads,
        }


# Instancia global — se carga una vez al arrancar el backend
# Se importa desde los demás módulos con: from backend.llm.engine import engine
engine = LLMEngine()
