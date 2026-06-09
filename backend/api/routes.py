"""
backend/api/routes.py
Endpoints FastAPI — Solo escucha en localhost:8765
Nunca expuesto a internet.
"""

import logging
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.storage.db import get_db, init_db, Conversation, Message, PortfolioItem
from backend.security.auth import auth_service
from backend.llm.engine import engine
from backend.llm.socratic import SocraticTutor, StudentContext, HintLevel
from backend.file_generator.generator import file_generator

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EduIA Backend",
    description="API local para EduIA — 100% local, sin internet",
    version="0.1.0",
    docs_url="/docs",       # Solo accesible desde localhost
    redoc_url="/redoc",
)

# CORS: solo permite peticiones desde localhost (Tauri usa localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "tauri://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# SCHEMAS (Pydantic)
# ─────────────────────────────────────────────

class StudentCreate(BaseModel):
    name: str
    pin: str
    course: str
    age: int

class TeacherCreate(BaseModel):
    name: str
    password: str
    subject: str = ""

class LoginRequest(BaseModel):
    name: str
    credential: str   # PIN para alumnos, contraseña para profesores
    role: str         # "student" o "teacher"

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    subject: str = "Programación"

class FileRequest(BaseModel):
    file_type: str         # "py", "html", etc.
    topic: str
    instructions: str
    evaluation_answers: Optional[list[str]] = None

class EvaluationAnswers(BaseModel):
    file_type: str
    topic: str
    answers: list[str]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_token(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    return authorization.split(" ")[1]

def require_student(
    db: Session = Depends(get_db),
    token: str = Depends(get_token)
):
    student = auth_service.get_current_student(db, token)
    if not student:
        raise HTTPException(status_code=401, detail="Sesión de alumno no válida")
    return student

def require_teacher(
    db: Session = Depends(get_db),
    token: str = Depends(get_token)
):
    teacher = auth_service.get_current_teacher(db, token)
    if not teacher:
        raise HTTPException(status_code=401, detail="Sesión de profesor no válida")
    return teacher


# ─────────────────────────────────────────────
# ENDPOINTS — SISTEMA
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Al arrancar: inicializar BD y cargar modelo."""
    init_db()
    logger.info("Cargando modelo LLM... (puede tardar 15-30 segundos)")
    engine.load()
    logger.info("✅ EduIA Backend listo en http://localhost:8765")

@app.on_event("shutdown")
async def shutdown():
    engine.unload()

@app.get("/")
def root():
    return {"status": "ok", "app": "EduIA", "version": "0.1.0"}

@app.get("/health")
def health():
    """La UI llama a este endpoint para saber si el backend está listo."""
    return {
        "status": "ok",
        "model_loaded": engine.is_loaded(),
        "model_info": engine.get_model_info(),
    }


# ─────────────────────────────────────────────
# ENDPOINTS — AUTENTICACIÓN
# ─────────────────────────────────────────────

@app.post("/auth/register/student")
def register_student(data: StudentCreate, db: Session = Depends(get_db)):
    try:
        student = auth_service.create_student(
            db, data.name, data.pin, data.course, data.age
        )
        return {"success": True, "student_id": student.id, "name": student.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/register/teacher")
def register_teacher(data: TeacherCreate, db: Session = Depends(get_db)):
    try:
        teacher = auth_service.create_teacher(db, data.name, data.password, data.subject)
        return {"success": True, "teacher_id": teacher.id, "name": teacher.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    if data.role == "student":
        token = auth_service.login_student(db, data.name, data.credential)
    elif data.role == "teacher":
        token = auth_service.login_teacher(db, data.name, data.credential)
    else:
        raise HTTPException(status_code=400, detail="Rol no válido")
    
    if not token:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    return {"success": True, "token": token, "role": data.role}

@app.post("/auth/logout")
def logout(token: str = Depends(get_token)):
    auth_service.logout(token)
    return {"success": True}


# ─────────────────────────────────────────────
# ENDPOINTS — CHAT (ALUMNOS)
# ─────────────────────────────────────────────

# Sesiones de chat activas en memoria
# { student_id: { conversation_id: StudentContext } }
_chat_sessions: dict = {}

@app.post("/chat/start")
def start_conversation(
    data: ChatMessage,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    """Inicia una nueva conversación."""
    conversation = Conversation(
        student_id=student.id,
        subject=data.subject,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    # Crear contexto de sesión
    context = StudentContext(
        student_id=student.id,
        name=student.name,
        course=student.course,
        age=student.age,
        subject=data.subject,
    )
    
    if student.id not in _chat_sessions:
        _chat_sessions[student.id] = {}
    _chat_sessions[student.id][conversation.id] = context
    
    return {"conversation_id": conversation.id, "subject": data.subject}

@app.post("/chat/message")
def send_message(
    data: ChatMessage,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    """Envía un mensaje y recibe respuesta socrática (sin streaming)."""
    context = _get_or_create_context(student, data)
    tutor = SocraticTutor()
    
    response = tutor.respond(data.message, context)
    
    # Guardar en BD
    if data.conversation_id:
        _save_message(db, data.conversation_id, "user", data.message)
        _save_message(db, data.conversation_id, "assistant", response)
    
    return {
        "response": response,
        "hints_used": context.hints_used_today,
    }

@app.post("/chat/message/stream")
async def send_message_stream(
    data: ChatMessage,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    """Envía mensaje con respuesta en streaming (token a token)."""
    context = _get_or_create_context(student, data)
    tutor = SocraticTutor()
    
    def generate():
        for token in tutor.respond_stream(data.message, context):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# ENDPOINTS — GENERADOR DE ARCHIVOS
# ─────────────────────────────────────────────

@app.post("/files/evaluate")
def evaluate_for_file(
    data: FileRequest,
    student = Depends(require_student),
):
    """
    Antes de generar un archivo, evalúa si el alumno entiende el tema.
    Retorna 3 preguntas de comprensión.
    """
    context = StudentContext(
        student_id=student.id,
        name=student.name,
        course=student.course,
        age=student.age,
        subject="Programación",
    )
    
    tutor = SocraticTutor()
    questions = tutor.generate_evaluation_questions(
        data.file_type, data.topic, context
    )
    
    return {
        "questions": questions,
        "file_type": data.file_type,
        "topic": data.topic,
    }

@app.post("/files/generate")
def generate_file(
    data: FileRequest,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    """
    Genera el archivo SI el alumno ha pasado la evaluación.
    Requiere evaluation_answers con las respuestas a las 3 preguntas.
    """
    context = StudentContext(
        student_id=student.id,
        name=student.name,
        course=student.course,
        age=student.age,
        subject="Programación",
    )
    
    # Verificar respuestas de evaluación
    if not data.evaluation_answers or len(data.evaluation_answers) < 3:
        raise HTTPException(
            status_code=400,
            detail="Debes responder las 3 preguntas de evaluación primero"
        )
    
    tutor = SocraticTutor()
    eval_result = tutor.evaluate_answers(data.topic, data.evaluation_answers, context)
    
    if not eval_result.get("comprende", False):
        return {
            "success": False,
            "message": eval_result.get("feedback", "Necesitas repasar el tema un poco más."),
            "siguiente_paso": eval_result.get("siguiente_paso", ""),
        }
    
    # Generar el archivo
    result = file_generator.generate(
        file_type=data.file_type,
        topic=data.topic,
        instructions=data.instructions,
        context=context,
        student_name=student.name,
    )
    
    # Guardar en portfolio
    if result["success"]:
        portfolio_item = PortfolioItem(
            student_id=student.id,
            filename=result["filename"],
            file_type=data.file_type,
            file_path=result["file_path"],
            subject="Programación",
            topic=data.topic,
            eval_passed=True,
        )
        db.add(portfolio_item)
        db.commit()
    
    return result

@app.get("/files/types")
def get_file_types():
    """Lista de tipos de archivo que puede generar la app."""
    return file_generator.get_supported_types()


# ─────────────────────────────────────────────
# ENDPOINTS — PORTFOLIO DEL ALUMNO
# ─────────────────────────────────────────────

@app.get("/portfolio")
def get_portfolio(
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    """Portfolio del alumno: todos sus archivos generados."""
    items = db.query(PortfolioItem).filter(
        PortfolioItem.student_id == student.id
    ).order_by(PortfolioItem.created_at.desc()).all()
    
    return {
        "student_name": student.name,
        "total_files": len(items),
        "items": [
            {
                "id": item.id,
                "filename": item.filename,
                "file_type": item.file_type,
                "topic": item.topic,
                "subject": item.subject,
                "eval_passed": item.eval_passed,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
    }

@app.get("/portfolio/{item_id}/content")
def get_file_content(
    item_id: int,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    """Lee el contenido de un archivo del portfolio."""
    import os
    item = db.query(PortfolioItem).filter(
        PortfolioItem.id == item_id,
        PortfolioItem.student_id == student.id,
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    if not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Archivo eliminado del disco")
    
    with open(item.file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return {"filename": item.filename, "content": content, "file_type": item.file_type}


# ─────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────

def _get_or_create_context(student, data: ChatMessage) -> StudentContext:
    """Recupera o crea el contexto de sesión del alumno."""
    conv_id = data.conversation_id or 0
    
    if student.id not in _chat_sessions:
        _chat_sessions[student.id] = {}
    
    if conv_id not in _chat_sessions[student.id]:
        _chat_sessions[student.id][conv_id] = StudentContext(
            student_id=student.id,
            name=student.name,
            course=student.course,
            age=student.age,
            subject=data.subject,
        )
    
    return _chat_sessions[student.id][conv_id]

def _save_message(db: Session, conv_id: int, role: str, content: str):
    msg = Message(conversation_id=conv_id, role=role, content=content)
    db.add(msg)
    db.commit()
