"""
backend/llm/guard.py
Segunda capa de seguridad socrática — idea de ChatGPT.
Si el modelo rompe el modo socrático y da una solución completa,
esta función la intercepta y devuelve una respuesta segura.
No es perfecta pero evita el desastre en demo.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Patrones que indican solución completa — modelos pequeños los generan
# incluso con buen prompt después de varios turnos
SOLUTION_PATTERNS = [
    r"^def\s+\w+",           # función Python
    r"^class\s+\w+",         # clase Python
    r"^import\s+\w+",        # import al inicio
    r"^from\s+\w+\s+import", # from import
    r"^<html",               # HTML completo
    r"^<!DOCTYPE",           # HTML completo
    r"for\s+\w+\s+in\s+",   # bucle for
    r"while\s+.+:",          # bucle while
]

# Si la respuesta tiene más de N líneas de código, sospechosa
CODE_BLOCK_THRESHOLD = 4

# Respuestas socráticas de seguridad — se usan cuando se detecta solución
SAFE_RESPONSES = [
    "Pregunta:\n¿Qué crees que debería hacer primero ese código?",
    "Pregunta:\n¿Puedes describir con tus palabras cómo funcionaría ese programa?",
    "Pista:\nIntenta pensar en los pasos antes de escribir código.\n\nPregunta:\n¿Cuál sería el primer paso?",
    "Pregunta:\n¿Qué parte del programa te parece más difícil de entender?",
]

_safe_idx = 0


def looks_like_full_solution(response: str) -> bool:
    """
    Detecta si la respuesta del modelo parece una solución completa.
    Heurística simple — no perfecta pero suficiente para la demo.
    """
    lines = response.strip().split("\n")

    # Contar líneas que parecen código
    code_lines = sum(
        1 for line in lines
        if line.startswith("    ") or  # indentación Python
           line.strip().startswith("def ") or
           line.strip().startswith("class ") or
           line.strip().startswith("import ") or
           line.strip().startswith("for ") or
           line.strip().startswith("while ") or
           line.strip().startswith("<") or  # HTML
           line.strip().endswith(":")
    )

    if code_lines >= CODE_BLOCK_THRESHOLD:
        logger.warning(
            "[GUARD] Solución completa detectada (%d líneas código). Interceptando.",
            code_lines
        )
        return True

    # Patrones en las primeras líneas
    first_lines = "\n".join(lines[:3])
    for pattern in SOLUTION_PATTERNS:
        if re.search(pattern, first_lines, re.MULTILINE | re.IGNORECASE):
            logger.warning("[GUARD] Patrón de solución detectado: %s", pattern)
            return True

    return False


def safe_socratic_response() -> str:
    """Devuelve una respuesta socrática segura de forma rotatoria."""
    global _safe_idx
    response = SAFE_RESPONSES[_safe_idx % len(SAFE_RESPONSES)]
    _safe_idx += 1
    return response


def guard_response(response: str, user_message: str = "") -> str:
    """
    Punto de entrada principal.
    Recibe la respuesta del modelo y la filtra si es necesario.
    Transparente si la respuesta es correcta.
    """
    if looks_like_full_solution(response):
        safe = safe_socratic_response()
        logger.warning("[GUARD] Respuesta reemplazada por: %s", safe[:50])
        return safe
    return response
