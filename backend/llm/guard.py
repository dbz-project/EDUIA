"""
backend/llm/guard.py
Segunda capa socrática — patrones ampliados según recomendación ChatGPT.
Mejor bloquear un falso positivo que dejar pasar una solución completa en demo.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Patrones ampliados — ChatGPT añadió import, print, from, if __name__
BLOCK_PATTERNS = [
    r"^\s*def\s+\w+",
    r"^\s*class\s+\w+",
    r"^\s*import\s+\w+",
    r"^\s*from\s+\w+\s+import",
    r"^\s*return\s+",
    r"^\s*for\s+\w+\s+in\s+",
    r"^\s*while\s+.+:",
    r"^\s*if\s+__name__",
    r"^\s*print\s*\(",
    r"^<html",
    r"^<!DOCTYPE",
    r"^\s*<body",
    r"^\s*<script",
]

CODE_LINE_THRESHOLD = 4

SAFE_RESPONSES = [
    "Pregunta:\n¿Qué crees que debería hacer primero ese código?",
    "Pregunta:\n¿Puedes describir con tus palabras cómo funcionaría ese programa?",
    "Pista:\nIntenta pensar en los pasos antes de escribir código.\n\nPregunta:\n¿Cuál sería el primer paso?",
    "Pregunta:\n¿Qué parte del programa te parece más difícil de entender?",
]
_safe_idx = 0


def looks_like_full_solution(response: str) -> bool:
    lines = response.strip().split("\n")

    code_lines = sum(
        1 for line in lines
        if (line.startswith("    ") or line.startswith("\t")) and line.strip()
    )
    if code_lines >= CODE_LINE_THRESHOLD:
        logger.warning("[GUARD] %d líneas indentadas — bloqueando", code_lines)
        return True

    for line in lines:
        for pattern in BLOCK_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                logger.warning("[GUARD] Patrón '%s' detectado", pattern)
                return True

    return False


# Alias para tests (nombre sugerido por ChatGPT)
def should_block(text: str) -> bool:
    return looks_like_full_solution(text)


def safe_socratic_response() -> str:
    global _safe_idx
    r = SAFE_RESPONSES[_safe_idx % len(SAFE_RESPONSES)]
    _safe_idx += 1
    return r


def guard_response(response: str, user_message: str = "") -> str:
    if looks_like_full_solution(response):
        safe = safe_socratic_response()
        logger.warning("[GUARD] Reemplazando respuesta → %s", safe[:40])
        return safe
    return response
