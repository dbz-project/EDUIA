"""
tests/test_guard.py
Tests del guard socrático — diseñados por ChatGPT, implementados por Claude.
Completamente deterministas, no necesitan modelo LLM.
Ejecutar: python -m pytest tests/test_guard.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm.guard import should_block, guard_response, safe_socratic_response


# ── Tests que DEBEN bloquear ──────────────────

def test_python_function():
    """Función Python completa debe bloquearse."""
    assert should_block("def suma(a, b):\n    return a + b")

def test_python_class():
    """Clase Python debe bloquearse."""
    assert should_block("class Persona:\n    pass")

def test_html_complete():
    """HTML completo debe bloquearse."""
    assert should_block("<html>\n<body>\n<h1>Hola</h1>\n</body>\n</html>")

def test_import_statement():
    """Import al inicio debe bloquearse — patrón añadido por ChatGPT."""
    assert should_block("import os\n\nprint('Hola')")

def test_from_import():
    """from...import debe bloquearse."""
    assert should_block("from math import sqrt\nresult = sqrt(16)")

def test_mixed_text_and_code():
    """Caso más importante según ChatGPT: texto + código mezclado."""
    assert should_block(
        "Para resolverlo puedes usar esto:\n\ndef suma(a, b):\n    return a + b"
    )

def test_indented_block():
    """Bloque con 4+ líneas indentadas debe bloquearse."""
    code = (
        "Aquí tienes:\n"
        "    x = 1\n"
        "    y = 2\n"
        "    z = x + y\n"
        "    print(z)\n"
    )
    assert should_block(code)

def test_while_loop():
    """Bucle while debe bloquearse."""
    assert should_block("while True:\n    print('hola')")

def test_for_loop():
    """Bucle for debe bloquearse."""
    assert should_block("for i in range(10):\n    print(i)")

def test_html_doctype():
    """DOCTYPE HTML debe bloquearse."""
    assert should_block("<!DOCTYPE html>\n<html>\n</html>")


# ── Tests que NO deben bloquearse ────────────

def test_normal_explanation():
    """Explicación educativa normal — NO bloquear."""
    assert not should_block(
        "Una función permite reutilizar código y organizar tareas."
    )

def test_socratic_hint():
    """Pista socrática — NO bloquear."""
    assert not should_block(
        "Pista:\nLas listas permiten guardar varios elementos.\n\n"
        "Pregunta:\n¿Qué tipo de datos necesitas almacenar?"
    )

def test_socratic_question():
    """Pregunta socrática — NO bloquear."""
    assert not should_block(
        "Pregunta:\n¿Qué parámetros debería recibir esa función?"
    )

def test_short_concept_answer():
    """Respuesta conceptual corta — NO bloquear."""
    assert not should_block(
        "Una variable es un espacio en memoria que guarda un valor."
    )

def test_mention_of_def_in_text():
    """Mencionar 'def' en texto explicativo — NO bloquear."""
    assert not should_block(
        "En Python, la palabra reservada def se usa para definir funciones."
    )


# ── Tests del guard_response ──────────────────

def test_guard_replaces_solution():
    """guard_response debe reemplazar código por respuesta socrática."""
    code = "def suma(a, b):\n    return a + b"
    result = guard_response(code)
    assert result != code
    assert "Pregunta:" in result or "Pista:" in result

def test_guard_passes_normal():
    """guard_response no debe modificar respuestas normales."""
    msg = "Pregunta:\n¿Qué has intentado hasta ahora?"
    assert guard_response(msg) == msg

def test_safe_responses_rotate():
    """Las respuestas de seguridad deben rotar."""
    r1 = safe_socratic_response()
    r2 = safe_socratic_response()
    r3 = safe_socratic_response()
    r4 = safe_socratic_response()
    r5 = safe_socratic_response()
    # Al menos dos deben ser distintas en 5 llamadas
    responses = {r1, r2, r3, r4, r5}
    assert len(responses) > 1


# ── Test manual rápido (ChatGPT) ──────────────

def test_quick_manual_samples():
    """
    Prueba manual de 30 segundos de ChatGPT.
    Resultado esperado: True, True, False, False
    """
    samples = [
        ("def suma(a,b): return a+b",                True),
        ("<html><body></body></html>",                True),
        ("¿Qué parámetros debería recibir?",         False),
        ("Una lista permite almacenar elementos.",    False),
    ]
    for text, expected in samples:
        result = should_block(text)
        assert result == expected, (
            f"FALLO: should_block({text!r}) = {result}, esperado {expected}"
        )


if __name__ == "__main__":
    # Ejecutable directamente sin pytest
    tests = [
        test_python_function, test_python_class, test_html_complete,
        test_import_statement, test_from_import, test_mixed_text_and_code,
        test_indented_block, test_while_loop, test_for_loop, test_html_doctype,
        test_normal_explanation, test_socratic_hint, test_socratic_question,
        test_short_concept_answer, test_mention_of_def_in_text,
        test_guard_replaces_solution, test_guard_passes_normal,
        test_safe_responses_rotate, test_quick_manual_samples,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
