"""
backend/file_generator/generator.py
Generador de archivos educativos (.py, .html, .css, .md, .js, .json, .txt)
Solo genera el archivo si el alumno ha demostrado comprensión del tema.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from backend.llm.engine import engine
from backend.llm.socratic import StudentContext

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {
    "py":   {"name": "Python",     "language": "python"},
    "html": {"name": "HTML",       "language": "html"},
    "css":  {"name": "CSS",        "language": "css"},
    "js":   {"name": "JavaScript", "language": "javascript"},
    "md":   {"name": "Markdown",   "language": "markdown"},
    "json": {"name": "JSON",       "language": "json"},
    "txt":  {"name": "Texto",      "language": "text"},
}

# ─────────────────────────────────────────────
# PROMPTS PARA GENERACIÓN DE ARCHIVOS
# ─────────────────────────────────────────────

FILE_GENERATION_PROMPT = """Eres EduIA generando un archivo educativo para un alumno de {age} años ({course}).
Asignatura: {subject}
Tipo de archivo: {file_type}
Tema: {topic}
Instrucciones del alumno: {instructions}

REGLAS DE GENERACIÓN:
1. El código/contenido debe ser EDUCATIVO — con comentarios que expliquen cada parte.
2. Nivel apropiado para {age} años.
3. Incluye comentarios en español que expliquen QUÉ hace cada parte y POR QUÉ.
4. El código debe ser funcional y correcto.
5. Añade al inicio un comentario con: autor (el alumno), fecha, descripción del archivo.
6. Para .py: incluye ejemplos de uso al final como comentarios.
7. Para .html: estructura semántica completa con comentarios.
8. NO incluyas nada que esté fuera del propósito educativo.

Genera SOLO el contenido del archivo, sin explicaciones adicionales fuera del código/contenido.
"""


class FileGenerator:
    """
    Genera archivos educativos con la IA.
    Requiere que el alumno haya pasado la evaluación previa de comprensión.
    """
    
    def __init__(self):
        self.engine = engine
    
    def generate(
        self,
        file_type: str,
        topic: str,
        instructions: str,
        context: StudentContext,
        student_name: str,
    ) -> dict:
        """
        Genera el archivo y lo guarda localmente.
        
        Retorna:
        {
            "success": bool,
            "filename": str,
            "content": str,
            "file_path": str,
            "explanation": str  # Explicación del archivo generado
        }
        """
        if file_type not in SUPPORTED_TYPES:
            return {
                "success": False,
                "error": f"Tipo de archivo '{file_type}' no soportado. "
                         f"Tipos disponibles: {', '.join(SUPPORTED_TYPES.keys())}",
            }
        
        try:
            # Generar contenido con la IA
            content = self._generate_content(file_type, topic, instructions, context)
            
            # Guardar archivo localmente
            file_path, filename = self._save_file(
                content, file_type, topic, student_name
            )
            
            # Generar explicación del archivo (para el aprendizaje)
            explanation = self._generate_explanation(content, file_type, topic, context)
            
            logger.info(f"Archivo generado: {filename} para alumno {student_name}")
            
            return {
                "success": True,
                "filename": filename,
                "content": content,
                "file_path": file_path,
                "explanation": explanation,
            }
            
        except Exception as e:
            logger.error(f"Error generando archivo: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_content(
        self,
        file_type: str,
        topic: str,
        instructions: str,
        context: StudentContext,
    ) -> str:
        """Genera el contenido del archivo con la IA."""
        prompt = FILE_GENERATION_PROMPT.format(
            age=context.age,
            course=context.course,
            subject=context.subject,
            file_type=SUPPORTED_TYPES[file_type]["name"],
            topic=topic,
            instructions=instructions,
        )
        
        content = self.engine.chat(
            system_prompt=prompt,
            user_message=f"Genera el archivo {file_type} sobre: {topic}",
        )
        
        # Limpiar posibles bloques markdown del modelo
        content = self._clean_code_blocks(content, file_type)
        return content
    
    def _save_file(
        self, content: str, file_type: str, topic: str, student_name: str
    ) -> tuple[str, str]:
        """
        Guarda el archivo en la carpeta de documentos del alumno.
        Windows: Documentos/EduIA/[nombre_alumno]/
        """
        if os.name == "nt":
            docs_dir = Path.home() / "Documents" / "EduIA" / student_name
        else:
            docs_dir = Path.home() / "EduIA" / student_name
        
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombre del archivo: tema_fecha.extension
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (" ", "-", "_"))
        safe_topic = safe_topic.replace(" ", "_")[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{safe_topic}_{timestamp}.{file_type}"
        
        file_path = docs_dir / filename
        file_path.write_text(content, encoding="utf-8")
        
        return str(file_path), filename
    
    def _generate_explanation(
        self,
        content: str,
        file_type: str,
        topic: str,
        context: StudentContext,
    ) -> str:
        """
        Genera una explicación del archivo para reforzar el aprendizaje.
        La IA explica qué hizo y por qué, adaptado a la edad del alumno.
        """
        explanation_prompt = f"""Explica este archivo {file_type} a un alumno de {context.age} años de forma clara y motivadora.
        
Archivo generado sobre: {topic}

Contenido:
{content[:500]}...

Explica en 3-4 frases:
1. Qué hace el archivo
2. Las partes más importantes
3. Qué podría mejorar o explorar el alumno a continuación

Tono: cercano, motivador, adaptado a {context.age} años."""
        
        return self.engine.chat(
            system_prompt="Eres un tutor explicando código/contenido a un estudiante.",
            user_message=explanation_prompt,
        )
    
    def _clean_code_blocks(self, content: str, file_type: str) -> str:
        """
        Elimina bloques markdown (```python ... ```) que el modelo puede añadir.
        """
        lines = content.strip().split("\n")
        
        # Eliminar primera línea si es un bloque de código
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        
        # Eliminar última línea si cierra un bloque
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        
        return "\n".join(lines)
    
    def get_supported_types(self) -> list[dict]:
        """Lista de tipos de archivo soportados para la UI."""
        return [
            {"extension": ext, "name": info["name"]}
            for ext, info in SUPPORTED_TYPES.items()
        ]


# Instancia global
file_generator = FileGenerator()
