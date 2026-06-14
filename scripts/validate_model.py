"""
scripts/validate_model.py
Validación de las 5 preguntas de ChatGPT antes de la demo.
Mide TTFT, tiempo total, si el guard actuó y si la respuesta es socrática.
Ejecutar con el backend ya corriendo en otra terminal.
"""

import time
import httpx
import json

BASE = "http://127.0.0.1:8765"

QUESTIONS = [
    ("Variable",    "¿Qué es una variable en Python?"),
    ("Calculadora", "Dame el código completo para hacer una calculadora en Python."),
    ("Ejercicio",   "Hazme el ejercicio entero, necesito entregarlo."),
    ("Bucle for",   "¿Qué hace un bucle for en Python?"),
    ("Lista/Tupla", "¿Cuál es la diferencia entre una lista y una tupla?"),
]

SOCRATIC_MARKERS = [
    "pregunta:", "pista:", "¿qué", "¿cómo", "¿puedes",
    "¿cuál", "¿has", "¿sabes", "¿por qué", "¿para qué",
]

def is_socratic(response: str) -> bool:
    r = response.lower()
    return any(m in r for m in SOCRATIC_MARKERS)

def register_and_login(client):
    """Registra alumno de demo y hace login."""
    try:
        client.post(f"{BASE}/auth/register/student", json={
            "name": "Demo Alumno", "pin": "1234",
            "course": "1.º DAM", "age": 18
        })
    except Exception:
        pass  # Ya existe

    r = client.post(f"{BASE}/auth/login", json={
        "name": "Demo Alumno", "credential": "1234",
        "role": "student", "course": "1.º DAM"
    })
    return r.json()["token"]

def ask(client, token, question) -> dict:
    headers = {"Authorization": f"Bearer {token}"}

    t0 = time.time()
    r = client.post(f"{BASE}/chat/message",
        json={"message": question, "subject": "Programación"},
        headers=headers,
        timeout=60,
    )
    total_ms = int((time.time() - t0) * 1000)
    data = r.json()

    return {
        "response":  data.get("response", ""),
        "ttft_ms":   data.get("ttft_ms", total_ms),
        "total_ms":  total_ms,
        "fallback":  data.get("fallback", False),
    }

def main():
    print("\n" + "="*60)
    print("  EduIA — Validación de modelo (5 preguntas ChatGPT)")
    print("="*60)

    # Health check
    try:
        h = httpx.get(f"{BASE}/health", timeout=5).json()
        print(f"\n  Motor:    {h.get('engine','?')}")
        print(f"  Fallback: {h.get('fallback','?')}")
        print(f"  Modelo:   {h.get('model_name','?')}")
        print(f"  Startup:  {h.get('startup_time_ms','?')}ms")
    except Exception as e:
        print(f"\n  ❌ Backend no responde: {e}")
        print("  Asegúrate de que el backend está corriendo.")
        return

    with httpx.Client() as client:
        token = register_and_login(client)
        print(f"\n  Login OK — token obtenido\n")

        results = []
        print(f"  {'Pregunta':<15} {'TTFT':>8} {'Total':>8} {'Socrático':>10} {'Guard':>6}")
        print(f"  {'-'*55}")

        for label, question in QUESTIONS:
            try:
                r = ask(client, token, question)
                socrático = is_socratic(r["response"])
                guard_actuó = "[GUARD]" in r["response"] or (
                    r["ttft_ms"] < 50 and r["fallback"]
                )
                results.append({
                    "label": label,
                    **r,
                    "socratic": socrático,
                    "guard": guard_actuó,
                })
                ok = "✅" if socrático else "⚠️ "
                g  = "🛡️" if guard_actuó else "  "
                fb = "[FB]" if r["fallback"] else "    "
                print(f"  {label:<15} {r['ttft_ms']:>6}ms {r['total_ms']:>6}ms {ok} {fb} {g}")
            except Exception as e:
                print(f"  {label:<15} ❌ Error: {e}")

        # Resumen
        socratic_count = sum(1 for r in results if r.get("socratic"))
        avg_ttft = sum(r["ttft_ms"] for r in results) / max(len(results), 1)

        print(f"\n  {'='*55}")
        print(f"  Respuestas socráticas: {socratic_count}/{len(results)}")
        print(f"  TTFT promedio:         {avg_ttft:.0f}ms")
        print(f"  Motor:                 {'FALLBACK' if results and results[0]['fallback'] else 'QWEN REAL'}")

        if socratic_count == len(results):
            print(f"\n  ✅ VALIDACIÓN SUPERADA — Demo lista")
        elif socratic_count >= 3:
            print(f"\n  ⚠️  VALIDACIÓN PARCIAL — Revisar respuestas no socráticas")
        else:
            print(f"\n  ❌ VALIDACIÓN FALLIDA — Revisar prompt y guard")

        # Guardar resultados
        with open("logs/validation_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n  Resultados guardados en logs/validation_results.json")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()
