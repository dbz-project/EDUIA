"""
backend/llm/socratic.py
Tutor socrático — La IA nunca da respuestas directas.
Guía al alumno mediante preguntas progresivas.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from backend.llm.engine import engine

logger = logging.getLogger(__name__)


class HintLevel(Enum):
    """Niveles de pista. La IA escala gradualmente."""
    QUESTION_ONLY = 0     # Solo hace preguntas, sin pistas
    SUBTLE_HINT   = 1     # Pista muy leve, orientativa
    CLEAR_HINT    = 2     # Pista clara pero sin resolver
    GUIDED_HELP   = 3     # Guía paso a paso sin dar el resultado


class RequestType(Enum):
    """Tipo de petición del alumno."""
    QUESTION       = "question"        # Pregunta sobre un concepto
    FILE_REQUEST   = "file_request"    # Pide que se genere un archivo
    CODE_HELP      = "code_help"       # Pide ayuda con código
    EXPLANATION    = "explanation"     # Pide explicación de algo
    DIRECT_ANSWER  = "direct_answer"   # Pide la respuesta directamente (hay que redirigir)


@dataclass
class StudentContext:
    """
    Contexto del alumno en la sesión actual.
    Se mantiene en memoria durante la conversación.
    """
    student_id: int
    name: str
    course: str               # "1ESO", "2ESO", "1Bach", etc.
    age: int
    subject: str              # "Programación", "Matemáticas", etc.
    hint_level: HintLevel = HintLevel.QUESTION_ONLY
    hints_used_today: int = 0
    conversation_history: list = field(default_factory=list)
    

# ─────────────────────────────────────────────
# SYSTEM PROMPTS — El alma de EduIA
# ─────────────────────────────────────────────

SOCRATIC_BASE_PROMPT = """Eres EduIA, un tutor de inteligencia artificial para estudiantes de entre {age_min} y {age_max} años en centros educativos españoles.

ASIGNATURA: {subject}
CURSO DEL ALUMNO: {course}
EDAD DEL ALUMNO: {age} años
PISTAS DADAS EN ESTA CONVERSACIÓN: {hints_used}

═══ TU FILOSOFÍA PEDAGÓGICA ═══
Tu objetivo NO es dar respuestas. Tu objetivo es que el alumno llegue a la respuesta por sí mismo.
Usas el método socrático: guías con preguntas, no con soluciones.

═══ REGLAS ESTRICTAS ═══
1. NUNCA des la respuesta directa a un ejercicio o problema.
2. Responde SIEMPRE con una pregunta que lleve al alumno a pensar.
3. Si el alumno lleva {hints_used} pistas y sigue bloqueado, da una pista más concreta (pero nunca la solución).
4. Adapta tu lenguaje a {age} años: claro, cercano, sin tecnicismos innecesarios.
5. Si el alumno está frustrado, reconócelo con empatía antes de continuar.
6. Celebra los avances aunque sean pequeños.
7. Si detectas que el alumno pegó código de internet, pregúntale que lo explique línea a línea.
8. NUNCA hagas el trabajo por el alumno.

═══ FORMATO DE RESPUESTAS ═══
- Respuestas cortas (2-4 frases máximo).
- Siempre termina con una pregunta.
- En español, tono cercano (tutéalo).
- No uses markdown complejo, solo texto simple.

═══ SEÑALES DE ALERTA ═══
Si el alumno escribe cosas como:
- "dame la solución", "resuelve esto", "hazme el ejercicio"
→ Responde: "Entiendo que quieres la respuesta rápida, pero aprenderás más si llegamos juntos. ¿Por dónde crees que podríamos empezar?"
"""

EVALUATION_PROMPT = """Eres EduIA evaluando si un alumno de {age} años ({course}) entiende un tema antes de ayudarle a crear un archivo.

El alumno ha pedido crear: {file_type}
Tema del archivo: {topic}
Asignatura: {subject}

Genera EXACTAMENTE 3 preguntas progresivas (de más fácil a más difícil) para evaluar si el alumno entiende el tema.
Las preguntas deben:
- Ser abiertas (no de sí/no)
- Estar adaptadas a {age} años
- Ir del concepto básico al aplicado
- Estar en español

Formato de respuesta:
PREGUNTA_1: [pregunta básica sobre el concepto]
PREGUNTA_2: [pregunta sobre cómo funciona]
PREGUNTA_3: [pregunta sobre para qué sirve o cómo se aplica]
"""

EVALUATION_FEEDBACK_PROMPT = """Eres EduIA. Un alumno de {age} años ha respondido preguntas de evaluación sobre {topic}.

Sus respuestas:
{answers}

Evalúa si el alumno tiene suficiente comprensión para crear el archivo solicitado.
Sé generoso: si entiende los conceptos básicos, aunque no perfectamente, ayúdale.

Responde en este formato:
COMPRENDE: SI/NO/PARCIAL
FEEDBACK: [1-2 frases de feedback motivador]
SIGUIENTE_PASO: [qué hacer ahora — ayudarle a crear el archivo, o qué necesita repasar]
"""


# ─────────────────────────────────────────────
# TUTOR SOCRÁTICO
# ─────────────────────────────────────────────

class SocraticTutor:
    """
    Implementa la pedagogía socrática.
    Nunca da respuestas directas. Siempre guía.
    """
    
    def __init__(self):
        self.engine = engine
    
    def respond(self, message: str, context: StudentContext) -> str:
        """
        Respuesta principal del tutor.
        Analiza el tipo de petición y responde de forma socrática.
        """
        request_type = self._classify_request(message)
        
        system_prompt = SOCRATIC_BASE_PROMPT.format(
            age_min=12,
            age_max=20,
            subject=context.subject,
            course=context.course,
            age=context.age,
            hints_used=context.hints_used_today,
        )
        
        # Si pide un archivo, redirigir al flujo de evaluación
        if request_type == RequestType.FILE_REQUEST:
            return self._handle_file_request(message, context)
        
        # Si pide respuesta directa, redirigir suavemente
        if request_type == RequestType.DIRECT_ANSWER:
            system_prompt += "\nEL ALUMNO ACABA DE PEDIR LA RESPUESTA DIRECTA. Recuérdale amablemente tu forma de trabajar y hazle una pregunta de orientación."
        
        response = self.engine.chat(
            system_prompt=system_prompt,
            user_message=message,
            conversation_history=context.conversation_history,
        )
        
        # Actualizar historial
        context.conversation_history.append({"role": "user", "content": message})
        context.conversation_history.append({"role": "assistant", "content": response})
        context.hints_used_today += 1
        
        return response
    
    def respond_stream(self, message: str, context: StudentContext):
        """Versión streaming de respond() para UX fluida."""
        system_prompt = SOCRATIC_BASE_PROMPT.format(
            age_min=12,
            age_max=20,
            subject=context.subject,
            course=context.course,
            age=context.age,
            hints_used=context.hints_used_today,
        )
        
        full_response = ""
        for token in self.engine.chat_stream(
            system_prompt=system_prompt,
            user_message=message,
            conversation_history=context.conversation_history,
        ):
            full_response += token
            yield token
        
        # Guardar en historial al terminar
        context.conversation_history.append({"role": "user", "content": message})
        context.conversation_history.append({"role": "assistant", "content": full_response})
        context.hints_used_today += 1
    
    def generate_evaluation_questions(
        self, 
        file_type: str, 
        topic: str, 
        context: StudentContext
    ) -> dict:
        """
        Genera 3 preguntas para evaluar comprensión antes de crear un archivo.
        Retorna dict con las 3 preguntas parseadas.
        """
        prompt = EVALUATION_PROMPT.format(
            age=context.age,
            course=context.course,
            file_type=file_type,
            topic=topic,
            subject=context.subject,
        )
        
        response = self.engine.chat(
            system_prompt="Eres un evaluador pedagógico. Sigue el formato exacto solicitado.",
            user_message=prompt,
        )
        
        return self._parse_evaluation_questions(response)
    
    def evaluate_answers(
        self,
        topic: str,
        answers: list[str],
        context: StudentContext,
    ) -> dict:
        """
        Evalúa las respuestas del alumno a las preguntas de comprensión.
        Retorna: {"comprende": bool, "feedback": str, "siguiente_paso": str}
        """
        answers_text = "\n".join([f"Respuesta {i+1}: {a}" for i, a in enumerate(answers)])
        
        prompt = EVALUATION_FEEDBACK_PROMPT.format(
            age=context.age,
            topic=topic,
            answers=answers_text,
        )
        
        response = self.engine.chat(
            system_prompt="Eres un evaluador pedagógico. Sigue el formato exacto.",
            user_message=prompt,
        )
        
        return self._parse_evaluation_feedback(response)
    
    def _handle_file_request(self, message: str, context: StudentContext) -> str:
        """
        Cuando el alumno pide un archivo, inicia el flujo de evaluación
        en lugar de generarlo directamente.
        """
        return (
            f"¡Buena idea crear ese archivo! Pero antes quiero asegurarme de que "
            f"entendemos bien el tema para que el resultado sea tuyo de verdad. "
            f"¿Te parece si te hago unas preguntas rápidas primero? "
            f"Escribe 'sí, empecemos' cuando estés listo. 😊"
        )
    
    def _classify_request(self, message: str) -> RequestType:
        """
        Clasifica el tipo de petición del alumno.
        Usa heurísticas simples para no gastar tokens del modelo.
        """
        message_lower = message.lower()
        
        # Detectar petición de archivo
        file_keywords = [
            ".py", ".html", ".css", ".js", ".md", ".json", ".txt",
            "crea un archivo", "hazme un archivo", "genera un archivo",
            "escribe el código", "dame el código completo",
        ]
        if any(kw in message_lower for kw in file_keywords):
            return RequestType.FILE_REQUEST
        
        # Detectar petición de respuesta directa
        direct_keywords = [
            "dame la solución", "dame la respuesta", "resuelve esto",
            "hazme el ejercicio", "dame el resultado", "cuál es la respuesta",
            "dime la respuesta", "soluciona esto",
        ]
        if any(kw in message_lower for kw in direct_keywords):
            return RequestType.DIRECT_ANSWER
        
        # Detectar petición de código
        code_keywords = ["código", "función", "clase", "script", "programa"]
        if any(kw in message_lower for kw in code_keywords):
            return RequestType.CODE_HELP
        
        return RequestType.QUESTION
    
    def _parse_evaluation_questions(self, response: str) -> dict:
        """Parsea las preguntas de evaluación del formato estructurado."""
        questions = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            if line.startswith("PREGUNTA_1:"):
                questions["q1"] = line.replace("PREGUNTA_1:", "").strip()
            elif line.startswith("PREGUNTA_2:"):
                questions["q2"] = line.replace("PREGUNTA_2:", "").strip()
            elif line.startswith("PREGUNTA_3:"):
                questions["q3"] = line.replace("PREGUNTA_3:", "").strip()
        
        # Fallback si el modelo no siguió el formato exacto
        if len(questions) < 3:
            questions = {
                "q1": "¿Qué sabes sobre este tema?",
                "q2": "¿Cómo funciona este concepto?",
                "q3": "¿Para qué lo usarías en un proyecto real?",
            }
        
        return questions
    
    def _parse_evaluation_feedback(self, response: str) -> dict:
        """Parsea la evaluación de respuestas del alumno."""
        result = {
            "comprende": False,
            "feedback": "",
            "siguiente_paso": "",
        }
        
        lines = response.strip().split("\n")
        for line in lines:
            if line.startswith("COMPRENDE:"):
                value = line.replace("COMPRENDE:", "").strip().upper()
                result["comprende"] = value in ["SI", "SÍ", "PARCIAL"]
            elif line.startswith("FEEDBACK:"):
                result["feedback"] = line.replace("FEEDBACK:", "").strip()
            elif line.startswith("SIGUIENTE_PASO:"):
                result["siguiente_paso"] = line.replace("SIGUIENTE_PASO:", "").strip()
        
        return result


# Instancia global
tutor = SocraticTutor()
