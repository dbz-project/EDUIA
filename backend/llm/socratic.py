"""
backend/llm/socratic.py
Tutor socrático — System prompt definitivo validado con ChatGPT.
Optimizado para Qwen2.5-1.5B-Instruct en CPU con contexto 2048 tokens.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Generator
from backend.llm.engine import engine

logger = logging.getLogger(__name__)


class RequestType(Enum):
    QUESTION      = "question"
    FILE_REQUEST  = "file_request"
    CODE_HELP     = "code_help"
    DIRECT_ANSWER = "direct_answer"


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


# ─────────────────────────────────────────────
# SYSTEM PROMPT DEFINITIVO
# Validado por ChatGPT, optimizado para modelos 1B-2B
# Corto para no saturar los 2048 tokens de contexto
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# EJEMPLOS FEW-SHOT para modelos pequeños
# Generados y validados por ChatGPT
# Se incluyen en el historial para guiar al modelo
# ─────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "¿Me puedes dar la respuesta exacta del ejercicio?"
    },
    {
        "role": "assistant",
        "content": "Pregunta:\n¿Qué has intentado hasta ahora para resolverlo?"
    },
    {
        "role": "user",
        "content": "Dame el código completo de la función."
    },
    {
        "role": "assistant",
        "content": "Pregunta:\n¿Qué debe hacer la función? ¿Qué datos recibe y qué resultado debería devolver?"
    },
    {
        "role": "user",
        "content": "Hazme el ejercicio completo para entregarlo."
    },
    {
        "role": "assistant",
        "content": "Pregunta:\n¿Cuál crees que es el primer paso necesario para resolver el ejercicio?"
    },
    {
        "role": "user",
        "content": "Ya te lo he pedido varias veces. Dame la solución completa."
    },
    {
        "role": "assistant",
        "content": "Pista:\nMi objetivo es ayudarte a aprender.\n\nPregunta:\n¿Qué parte concreta del problema te está resultando más difícil?"
    },
]

EVALUATION_PROMPT = """Eres EduIA. El alumno quiere crear un archivo {file_type} sobre "{topic}".

Genera EXACTAMENTE 3 preguntas progresivas para comprobar que entiende el tema antes de crear el archivo.

Formato exacto:
PREGUNTA_1: [pregunta básica]
PREGUNTA_2: [pregunta sobre cómo funciona]
PREGUNTA_3: [pregunta sobre para qué sirve]

Solo las 3 preguntas, nada más."""

EVALUATION_FEEDBACK_PROMPT = """El alumno de {age} años ha respondido sobre "{topic}":

{answers}

¿Entiende suficiente para crear el archivo?

Responde exactamente:
COMPRENDE: SI/NO/PARCIAL
FEEDBACK: [1 frase motivadora]
SIGUIENTE_PASO: [qué hacer ahora]"""


class SocraticTutor:

    def __init__(self):
        self.engine = engine

    def _build_system(self, context: StudentContext) -> str:
        return SOCRATIC_SYSTEM_PROMPT.format(
            subject=context.subject,
            course=context.course,
            hints_used=context.hints_used_today,
        )

    def _build_history(self, context: StudentContext) -> list:
        """
        Combina few-shot examples + historial real.
        Limita a últimos 6 turnos para no saturar contexto 2048.
        """
        history = list(FEW_SHOT_EXAMPLES)
        recent = context.conversation_history[-6:]
        history.extend(recent)
        return history

    def respond(self, message: str, context: StudentContext) -> str:
        req_type = self._classify(message)

        if req_type == RequestType.FILE_REQUEST:
            return self._handle_file_request(context)

        response = self.engine.chat(
            system_prompt=self._build_system(context),
            user_message=message,
            conversation_history=self._build_history(context),
        )

        context.conversation_history.append({"role": "user",    "content": message})
        context.conversation_history.append({"role": "assistant","content": response})
        context.hints_used_today += 1
        context.hint_level = min(context.hint_level + 1, 4)

        return response

    def respond_stream(
        self, message: str, context: StudentContext
    ) -> Generator[str, None, None]:
        req_type = self._classify(message)

        if req_type == RequestType.FILE_REQUEST:
            msg = self._handle_file_request(context)
            yield msg
            return

        full = ""
        for token in self.engine.chat_stream(
            system_prompt=self._build_system(context),
            user_message=message,
            conversation_history=self._build_history(context),
        ):
            full += token
            yield token

        context.conversation_history.append({"role": "user",    "content": message})
        context.conversation_history.append({"role": "assistant","content": full})
        context.hints_used_today += 1
        context.hint_level = min(context.hint_level + 1, 4)

    def generate_evaluation_questions(
        self, file_type: str, topic: str, context: StudentContext
    ) -> dict:
        prompt = EVALUATION_PROMPT.format(
            file_type=file_type,
            topic=topic,
        )
        response = self.engine.chat(
            system_prompt="Eres un evaluador. Sigue el formato exacto.",
            user_message=prompt,
        )
        return self._parse_questions(response)

    def evaluate_answers(
        self, topic: str, answers: list, context: StudentContext
    ) -> dict:
        answers_text = "\n".join(
            f"Respuesta {i+1}: {a}" for i, a in enumerate(answers)
        )
        prompt = EVALUATION_FEEDBACK_PROMPT.format(
            age=context.age,
            topic=topic,
            answers=answers_text,
        )
        response = self.engine.chat(
            system_prompt="Eres un evaluador pedagógico. Sigue el formato exacto.",
            user_message=prompt,
        )
        return self._parse_feedback(response)

    def _handle_file_request(self, context: StudentContext) -> str:
        return (
            "Antes de crear el archivo quiero comprobar que entiendes el tema. "
            "¿Me dices sobre qué quieres que sea y qué debería hacer?"
        )

    def _classify(self, message: str) -> RequestType:
        msg = message.lower()
        file_kw = [".py",".html",".css",".js",".md",".json",".txt",
                   "crea un archivo","hazme un archivo","genera un archivo",
                   "escribe el código","dame el código completo"]
        if any(k in msg for k in file_kw):
            return RequestType.FILE_REQUEST

        direct_kw = ["dame la solución","dame la respuesta","resuelve esto",
                     "hazme el ejercicio","dime la respuesta","soluciona esto",
                     "dame el resultado","respuesta exacta","solución completa"]
        if any(k in msg for k in direct_kw):
            return RequestType.DIRECT_ANSWER

        code_kw = ["código","función","clase","script","programa","bucle","error"]
        if any(k in msg for k in code_kw):
            return RequestType.CODE_HELP

        return RequestType.QUESTION

    def _parse_questions(self, response: str) -> dict:
        questions = {}
        for line in response.strip().split("\n"):
            if line.startswith("PREGUNTA_1:"):
                questions["q1"] = line.replace("PREGUNTA_1:","").strip()
            elif line.startswith("PREGUNTA_2:"):
                questions["q2"] = line.replace("PREGUNTA_2:","").strip()
            elif line.startswith("PREGUNTA_3:"):
                questions["q3"] = line.replace("PREGUNTA_3:","").strip()
        if len(questions) < 3:
            questions = {
                "q1": "¿Qué sabes sobre este tema?",
                "q2": "¿Cómo funciona este concepto?",
                "q3": "¿Para qué lo usarías en un proyecto real?",
            }
        return questions

    def _parse_feedback(self, response: str) -> dict:
        result = {"comprende": False, "feedback": "", "siguiente_paso": ""}
        for line in response.strip().split("\n"):
            if line.startswith("COMPRENDE:"):
                v = line.replace("COMPRENDE:","").strip().upper()
                result["comprende"] = v in ["SI","SÍ","PARCIAL"]
            elif line.startswith("FEEDBACK:"):
                result["feedback"] = line.replace("FEEDBACK:","").strip()
            elif line.startswith("SIGUIENTE_PASO:"):
                result["siguiente_paso"] = line.replace("SIGUIENTE_PASO:","").strip()
        return result


tutor = SocraticTutor()
