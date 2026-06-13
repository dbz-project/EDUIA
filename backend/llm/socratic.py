"""
backend/llm/socratic.py
Tutor socrático con guard integrado (mitigación ChatGPT riesgo #2).
Evaluación con umbral generoso (mitigación ChatGPT riesgo #1).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Generator
from backend.llm.guard import guard_response

logger = logging.getLogger(__name__)


@dataclass
class StudentContext:
    student_id: int
    name: str
    course: str
    age: int
    subject: str
    hint_level: int = 0
    hints_used_today: int = 0
    conversation_history: list = field(default_factory=list)
    pending_file_type: Optional[str] = None
    pending_eval: Optional[dict] = None
    eval_attempts: int = 0  # mitigación bucle infinito ChatGPT riesgo #1C


SOCRATIC_SYSTEM_PROMPT = """Eres EduIA, un tutor educativo para estudiantes de 12 a 20 años.

OBJETIVO:
Ayudar al alumno a aprender por sí mismo. No resuelves ejercicios ni entregas respuestas finales. Guías mediante preguntas y pistas progresivas.

REGLA PRINCIPAL:
Nunca des directamente la solución completa de una tarea, ejercicio, examen, problema o código.

Si el alumno pide la respuesta:
- No la des.
- Haz una pregunta que le ayude a pensar.
- Ofrécele una pista adecuada a su nivel.

NIVELES DE AYUDA:
Nivel 1: Haz una pregunta orientadora. No des información nueva importante.
Nivel 2: Da una pista breve. Mantén parte del trabajo para el alumno.
Nivel 3: Da una pista fuerte. Explica el siguiente paso sin resolver todo.
Nivel 4: Explica el procedimiento paso a paso. Sigue sin dar la respuesta final.

REGLAS:
1. Nunca entregues la solución final.
2. Nunca escribas ejercicios completos resueltos.
3. Nunca generes código completo sin evaluación previa.
4. Antes de ayudar, comprueba qué sabe el alumno.
5. Haz preguntas cortas y claras.
6. Usa español sencillo.
7. Si el alumno está bloqueado, sube solo un nivel de ayuda cada vez.
8. Si el alumno responde correctamente, felicítalo y avanza.
9. Si el alumno insiste en pedir la respuesta, mantén el enfoque socrático.
10. Si el alumno muestra comprensión suficiente, resume lo aprendido en una frase.

FORMATO:
Pregunta:
...

o

Pista:
...
Pregunta:
...

RECUERDA:
Tu éxito no es resolver problemas. Tu éxito es que el alumno los resuelva.

ASIGNATURA: {subject}
CURSO: {course}
PISTAS USADAS HOY: {hints_used}"""


FEW_SHOT_EXAMPLES = [
    {"role":"user","content":"¿Me puedes dar la respuesta exacta del ejercicio?"},
    {"role":"assistant","content":"Pregunta:\n¿Qué has intentado hasta ahora para resolverlo?"},
    {"role":"user","content":"Dame el código completo de la función."},
    {"role":"assistant","content":"Pregunta:\n¿Qué debe hacer la función? ¿Qué datos recibe y qué resultado debería devolver?"},
    {"role":"user","content":"Hazme el ejercicio completo para entregarlo."},
    {"role":"assistant","content":"Pregunta:\n¿Cuál crees que es el primer paso necesario para resolver el ejercicio?"},
    {"role":"user","content":"Ya te lo he pedido varias veces. Dame la solución completa."},
    {"role":"assistant","content":"Pista:\nMi objetivo es ayudarte a aprender.\n\nPregunta:\n¿Qué parte concreta del problema te está resultando más difícil?"},
]

EVALUATION_PROMPT = """Eres EduIA. El alumno quiere crear un archivo {file_type} sobre "{topic}".

Genera EXACTAMENTE 3 preguntas progresivas para comprobar que entiende el tema.

Formato exacto:
PREGUNTA_1: [pregunta básica]
PREGUNTA_2: [pregunta sobre cómo funciona]
PREGUNTA_3: [pregunta sobre para qué sirve]

Solo las 3 preguntas, nada más."""

# Umbral generoso — ChatGPT riesgo #1A
# Para la demo: aprobar si hay comprensión básica
# Mejor falso positivo que falso negativo
EVALUATION_FEEDBACK_PROMPT = """El alumno quiere crear un archivo {file_type} sobre "{topic}".

Sus respuestas a las preguntas de evaluación:
{answers}

CRITERIO GENEROSO: aprueba si el alumno demuestra comprensión BÁSICA del tema.
Un "dato que guarda información" para variable → APRUEBA.
Respuestas muy cortas pero coherentes → APRUEBA.
Solo rechaza si las respuestas son completamente incoherentes o vacías.

Responde exactamente:
COMPRENDE: SI/NO/PARCIAL
FEEDBACK: [1 frase motivadora]
SIGUIENTE_PASO: [qué hacer ahora]"""

# Máximo intentos de evaluación — evita bucle infinito (ChatGPT riesgo #1C)
MAX_EVAL_ATTEMPTS = 2


class SocraticTutor:

    def __init__(self):
        # engine se inyecta desde routes.py (real o fallback)
        from backend.llm.engine import engine
        self.engine = engine

    def _sys(self, ctx: StudentContext) -> str:
        return SOCRATIC_SYSTEM_PROMPT.format(
            subject=ctx.subject,
            course=ctx.course,
            hints_used=ctx.hints_used_today,
        )

    def _history(self, ctx: StudentContext) -> list:
        h = list(FEW_SHOT_EXAMPLES)
        h.extend(ctx.conversation_history[-6:])
        return h

    def respond(self, message: str, ctx: StudentContext) -> str:
        if self._classify(message) == "file":
            return self._handle_file(ctx)

        raw = self.engine.chat(
            system_prompt=self._sys(ctx),
            user_message=message,
            conversation_history=self._history(ctx),
        )

        # Segunda capa socrática (ChatGPT riesgo #2)
        response = guard_response(raw, message)

        ctx.conversation_history.append({"role":"user",     "content":message})
        ctx.conversation_history.append({"role":"assistant","content":response})
        ctx.hints_used_today += 1
        ctx.hint_level = min(ctx.hint_level + 1, 4)
        return response

    def respond_stream(self, message: str, ctx: StudentContext) -> Generator[str, None, None]:
        if self._classify(message) == "file":
            yield self._handle_file(ctx)
            return

        full = ""
        for token in self.engine.chat_stream(
            system_prompt=self._sys(ctx),
            user_message=message,
            conversation_history=self._history(ctx),
        ):
            full += token
            yield token

        # Guard al finalizar el stream
        guarded = guard_response(full, message)
        if guarded != full:
            # La respuesta fue reemplazada — comunicar al cliente
            yield "\n\n[GUARD_REPLACE]" + guarded

        ctx.conversation_history.append({"role":"user",     "content":message})
        ctx.conversation_history.append({"role":"assistant","content":guarded})
        ctx.hints_used_today += 1
        ctx.hint_level = min(ctx.hint_level + 1, 4)

    def generate_evaluation_questions(self, file_type, topic, ctx) -> dict:
        prompt = EVALUATION_PROMPT.format(file_type=file_type, topic=topic)
        resp = self.engine.chat(
            system_prompt="Eres un evaluador. Sigue el formato exacto.",
            user_message=prompt,
        )
        return self._parse_q(resp)

    def evaluate_answers(self, topic, file_type, answers, ctx) -> dict:
        ctx.eval_attempts += 1

        # Mitigación bucle infinito (ChatGPT riesgo #1C)
        # Al 2º intento, aprobar automáticamente
        if ctx.eval_attempts >= MAX_EVAL_ATTEMPTS:
            logger.info("[EVAL] Máx intentos alcanzado — aprobando automáticamente")
            return {
                "comprende": True,
                "feedback": "¡Bien hecho! Vamos a crear el archivo.",
                "siguiente_paso": "Generar el archivo.",
            }

        answers_text = "\n".join(f"Respuesta {i+1}: {a}" for i,a in enumerate(answers))
        prompt = EVALUATION_FEEDBACK_PROMPT.format(
            file_type=file_type,
            topic=topic,
            answers=answers_text,
        )
        resp = self.engine.chat(
            system_prompt="Eres un evaluador pedagógico generoso. Sigue el formato exacto.",
            user_message=prompt,
        )
        return self._parse_fb(resp)

    def _handle_file(self, ctx) -> str:
        return (
            "Antes de crear el archivo quiero comprobar que entiendes el tema. "
            "¿Me dices sobre qué quieres que sea y qué debería hacer?"
        )

    def _classify(self, msg: str) -> str:
        m = msg.lower()
        file_kw = [".py",".html",".css",".js",".md",".json",".txt",
                   "crea un archivo","hazme un archivo","genera un archivo"]
        if any(k in m for k in file_kw):
            return "file"
        return "chat"

    def _parse_q(self, resp: str) -> dict:
        q = {}
        for line in resp.strip().split("\n"):
            if line.startswith("PREGUNTA_1:"): q["q1"] = line.split(":",1)[1].strip()
            elif line.startswith("PREGUNTA_2:"): q["q2"] = line.split(":",1)[1].strip()
            elif line.startswith("PREGUNTA_3:"): q["q3"] = line.split(":",1)[1].strip()
        if len(q) < 3:
            q = {
                "q1": "¿Qué sabes sobre este tema?",
                "q2": "¿Cómo funciona este concepto?",
                "q3": "¿Para qué lo usarías?",
            }
        return q

    def _parse_fb(self, resp: str) -> dict:
        r = {"comprende": False, "feedback": "", "siguiente_paso": ""}
        for line in resp.strip().split("\n"):
            if line.startswith("COMPRENDE:"):
                v = line.split(":",1)[1].strip().upper()
                r["comprende"] = v in ["SI","SÍ","PARCIAL"]
            elif line.startswith("FEEDBACK:"):
                r["feedback"] = line.split(":",1)[1].strip()
            elif line.startswith("SIGUIENTE_PASO:"):
                r["siguiente_paso"] = line.split(":",1)[1].strip()
        return r


tutor = SocraticTutor()
