"""
backend/llm/fallback.py
Motor socrático de emergencia — generado por ChatGPT, integrado por Claude.
Se activa automáticamente si el modelo real no carga en 30 segundos.
El alumno nunca sabe que está en modo fallback.
"""

from __future__ import annotations
import logging
from typing import Generator

logger = logging.getLogger(__name__)


class FallbackEngine:
    """
    Motor socrático de emergencia sin dependencias externas.
    Misma interfaz que LLMEngine para sustitución transparente.
    Respuestas deterministas basadas en palabras clave.
    Tiempo de respuesta: instantáneo.
    """

    def __init__(self):
        logger.warning("=" * 50)
        logger.warning("[FALLBACK] ACTIVE — Modelo real no disponible")
        logger.warning("[FALLBACK] El alumno NO ve este mensaje")
        logger.warning("=" * 50)

    # ── API pública — igual que LLMEngine ─────────

    def is_loaded(self) -> bool:
        return True  # El fallback siempre está "disponible"

    def load(self) -> bool:
        return True

    def chat(
        self,
        system_prompt: str = "",
        user_message: str = "",
        conversation_history=None,
        **kwargs,
    ) -> str:
        logger.debug("[FALLBACK] Generando respuesta para: %s", user_message[:50])
        return self._generate(user_message)

    def chat_stream(
        self,
        system_prompt: str = "",
        user_message: str = "",
        conversation_history=None,
        **kwargs,
    ) -> Generator[str, None, None]:
        logger.debug("[FALLBACK] Stream para: %s", user_message[:50])
        yield self._generate(user_message)

    def get_model_info(self) -> dict:
        return {
            "loaded": True,
            "model_name": "EduIA Tutor",  # No revelar que es fallback
            "mode": "fallback",
        }

    def unload(self):
        pass

    # ── Lógica interna ─────────────────────────────

    def _generate(self, message: str) -> str:
        text = message.lower().strip()

        # Código completo / solución directa
        if any(w in text for w in [
            "código completo","codigo completo","hazme el código",
            "dame la solución","dame la respuesta","dime la respuesta",
            "solución completa","hazme el ejercicio","resuélvelo",
            "respuesta exacta","solucion",
        ]):
            return (
                "Pregunta:\n"
                "¿Qué has intentado hasta ahora para resolverlo?"
            )

        # Archivo
        if any(w in text for w in [
            ".py",".html",".css",".js",".md",".json",
            "crea un archivo","genera un archivo","hazme un archivo",
        ]):
            return (
                "Pregunta:\n"
                "Antes de crear el archivo, "
                "¿puedes explicar con tus palabras qué debería hacer?"
            )

        # Bucles
        if any(w in text for w in [
            "for","while","bucle","loop","iteración","repetir",
        ]):
            return (
                "Pista:\n"
                "Los bucles sirven para repetir acciones.\n\n"
                "Pregunta:\n"
                "¿Qué tarea necesitas repetir varias veces en tu programa?"
            )

        # Funciones
        if any(w in text for w in [
            "función","funcion","def ","return","parámetro","argumento",
        ]):
            return (
                "Pista:\n"
                "Las funciones agrupan código para reutilizarlo.\n\n"
                "Pregunta:\n"
                "¿Qué tarea concreta debería realizar esa función?"
            )

        # Listas
        if any(w in text for w in [
            "lista","listas","append","array","elemento",
        ]):
            return (
                "Pista:\n"
                "Las listas permiten guardar varios elementos juntos.\n\n"
                "Pregunta:\n"
                "¿Qué tipo de datos necesitas almacenar?"
            )

        # Diccionarios
        if any(w in text for w in [
            "diccionario","dict","clave","key","valor","value",
        ]):
            return (
                "Pista:\n"
                "Los diccionarios guardan pares clave-valor.\n\n"
                "Pregunta:\n"
                "¿Qué información quieres relacionar entre sí?"
            )

        # Errores
        if any(w in text for w in [
            "error","exception","traceback","no funciona","falla",
            "no me sale","bug",
        ]):
            return (
                "Pregunta:\n"
                "¿Puedes mostrarme el mensaje de error exacto "
                "y la línea donde ocurre?"
            )

        # Clases / POO
        if any(w in text for w in [
            "clase","class","objeto","herencia","método","instancia",
        ]):
            return (
                "Pista:\n"
                "Las clases son plantillas para crear objetos.\n\n"
                "Pregunta:\n"
                "¿Qué características y acciones debería tener ese objeto?"
            )

        # Variables / tipos
        if any(w in text for w in [
            "variable","int","str","float","bool","tipo","dato",
        ]):
            return (
                "Pista:\n"
                "Las variables guardan información que puede cambiar.\n\n"
                "Pregunta:\n"
                "¿Qué información necesitas guardar en ese momento del programa?"
            )

        # HTML / Web
        if any(w in text for w in [
            "html","css","web","página","etiqueta","tag","estilo",
        ]):
            return (
                "Pista:\n"
                "HTML estructura el contenido y CSS define su apariencia.\n\n"
                "Pregunta:\n"
                "¿Qué elemento quieres crear o modificar?"
            )

        # Insistencia
        if any(w in text for w in [
            "por favor","te lo pido","varias veces","ya te dije",
            "no entiendes","ayúdame ya",
        ]):
            return (
                "Pista:\n"
                "Mi objetivo es que aprendas, no darte la solución.\n\n"
                "Pregunta:\n"
                "¿Qué parte concreta te está resultando más difícil? "
                "Vamos paso a paso."
            )

        # General
        return (
            "Pregunta:\n"
            "¿Puedes darme un poco más de contexto "
            "para ayudarte mejor?"
        )
