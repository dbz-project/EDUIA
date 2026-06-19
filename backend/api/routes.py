"""
backend/api/routes.py — CORS ampliado para Tauri
"""

import time
import logging
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.storage.db import get_db, init_db, Conversation, Message, PortfolioItem
from backend.security.auth import auth_service
from backend.llm.fallback import FallbackEngine

logger = logging.getLogger(__name__)
_START_TIME = time.time()

app = FastAPI(title="EduIA", version="0.1.0", docs_url="/docs")

# CORS ampliado — incluye todos los orígenes posibles de Tauri
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
        "*",  # Demo: permitir todo origen local
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = None
_is_fallback = False


# ── Schemas ────────────────────────────────────

class StudentCreate(BaseModel):
    name: str
    pin: str
    course: str
    age: int

class LoginRequest(BaseModel):
    name: str
    credential: str
    role: str
    course: str = ""

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    subject: str = "Programación"

class FileRequest(BaseModel):
    file_type: str
    topic: str
    instructions: str
    evaluation_answers: Optional[list] = None


# ── Helpers ────────────────────────────────────

def get_token(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    return authorization.split(" ")[1]

def require_student(db: Session = Depends(get_db), token: str = Depends(get_token)):
    student = auth_service.get_current_student(db, token)
    if not student:
        raise HTTPException(status_code=401, detail="Sesion no valida")
    return student


# ── Arranque ───────────────────────────────────

@app.on_event("startup")
async def startup():
    global _engine, _is_fallback
    init_db()
    logger.info("Cargando motor LLM...")
    from backend.llm.engine import get_engine
    _engine = get_engine()
    _is_fallback = isinstance(_engine, FallbackEngine)
    if _is_fallback:
        logger.warning("[FALLBACK] Demo en modo fallback")
    else:
        logger.info("[OK] Motor LLM real activo")

@app.on_event("shutdown")
async def shutdown():
    if _engine and hasattr(_engine, "unload"):
        _engine.unload()


# ── Health check ───────────────────────────────

@app.get("/health")
def health():
    startup_ms = int((time.time() - _START_TIME) * 1000)
    model_info = _engine.get_model_info() if _engine else {}
    return {
        "status":          "ok",
        "ready":           _engine is not None,
        "model_loaded":    _engine.is_loaded() if _engine else False,
        "engine":          "fallback" if _is_fallback else "llm",
        "model_name":      model_info.get("model_name", "-"),
        "fallback":        _is_fallback,
        "startup_time_ms": startup_ms,
        "version":         "0.1.0",
    }


# ── Auth ───────────────────────────────────────

@app.post("/auth/register/student")
def register_student(data: StudentCreate, db: Session = Depends(get_db)):
    try:
        s = auth_service.create_student(db, data.name, data.pin, data.course, data.age)
        return {"success": True, "student_id": s.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    if data.role == "student":
        token = auth_service.login_student(db, data.name, data.credential)
    else:
        raise HTTPException(status_code=400, detail="Rol no valido")
    if not token:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"success": True, "token": token, "role": data.role}

@app.post("/auth/logout")
def logout(token: str = Depends(get_token)):
    auth_service.logout(token)
    return {"success": True}


# ── Chat ───────────────────────────────────────

_chat_sessions: dict = {}

@app.post("/chat/start")
def start_conversation(
    data: ChatMessage,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    conv = Conversation(student_id=student.id, subject=data.subject)
    db.add(conv); db.commit(); db.refresh(conv)
    _init_session(student, data)
    return {"conversation_id": conv.id, "subject": data.subject}

@app.post("/chat/message")
def send_message(
    data: ChatMessage,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    from backend.llm.socratic import SocraticTutor
    context = _get_context(student, data)
    tutor   = SocraticTutor()
    tutor.engine = _engine

    t0 = time.time()
    response = tutor.respond(data.message, context)
    ttft_ms  = int((time.time() - t0) * 1000)
    logger.info(f"TTFT: {ttft_ms}ms")

    if data.conversation_id:
        _save_msg(db, data.conversation_id, "user",      data.message)
        _save_msg(db, data.conversation_id, "assistant", response)

    return {
        "response":   response,
        "hints_used": context.hints_used_today,
        "ttft_ms":    ttft_ms,
        "fallback":   _is_fallback,
    }

@app.post("/chat/message/stream")
async def send_message_stream(
    data: ChatMessage,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    from backend.llm.socratic import SocraticTutor
    context = _get_context(student, data)
    tutor   = SocraticTutor()
    tutor.engine = _engine

    def generate():
        t0 = time.time(); first = True
        for token in tutor.respond_stream(data.message, context):
            if first:
                logger.info(f"TTFT stream: {int((time.time()-t0)*1000)}ms")
                first = False
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Archivos ───────────────────────────────────

@app.post("/files/evaluate")
def evaluate_for_file(data: FileRequest, student = Depends(require_student)):
    from backend.llm.socratic import SocraticTutor
    ctx   = _make_context(student)
    tutor = SocraticTutor(); tutor.engine = _engine
    q     = tutor.generate_evaluation_questions(data.file_type, data.topic, ctx)
    return {"questions": q, "file_type": data.file_type, "topic": data.topic}

@app.post("/files/generate")
def generate_file(
    data: FileRequest,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
    from backend.llm.socratic import SocraticTutor
    from backend.file_generator.generator import file_generator

    if not data.evaluation_answers or len(data.evaluation_answers) < 3:
        raise HTTPException(status_code=400, detail="Faltan respuestas de evaluacion")

    ctx   = _make_context(student)
    tutor = SocraticTutor(); tutor.engine = _engine
    eval_result = tutor.evaluate_answers(data.topic, data.file_type, data.evaluation_answers, ctx)

    if not eval_result.get("comprende", False):
        return {
            "success":        False,
            "message":        eval_result.get("feedback", "Repasa el tema."),
            "siguiente_paso": eval_result.get("siguiente_paso", ""),
        }

    result = file_generator.generate(
        file_type=data.file_type,
        topic=data.topic,
        instructions=data.instructions,
        context=ctx,
        student_name=student.name,
    )

    if result.get("success"):
        item = PortfolioItem(
            student_id=student.id,
            filename=result["filename"],
            file_type=data.file_type,
            file_path=result["file_path"],
            subject=ctx.subject,
            topic=data.topic,
            eval_passed=True,
        )
        db.add(item); db.commit()

    return result

@app.get("/files/types")
def get_file_types():
    from backend.file_generator.generator import file_generator
    return file_generator.get_supported_types()


# ── Portfolio ──────────────────────────────────

@app.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db), student = Depends(require_student)):
    items = db.query(PortfolioItem).filter(
        PortfolioItem.student_id == student.id
    ).order_by(PortfolioItem.created_at.desc()).all()
    return {
        "student_name": student.name,
        "total_files":  len(items),
        "items": [
            {
                "id":          i.id,
                "filename":    i.filename,
                "file_type":   i.file_type,
                "topic":       i.topic,
                "subject":     i.subject,
                "eval_passed": i.eval_passed,
                "created_at":  i.created_at.isoformat(),
            }
            for i in items
        ],
    }

@app.get("/portfolio/{item_id}/content")
def get_file_content(
    item_id: int,
    db: Session = Depends(get_db),
    student = Depends(require_student),
):
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


# ── Helpers internos ───────────────────────────

def _init_session(student, data):
    from backend.llm.socratic import StudentContext
    sid = student.id
    if sid not in _chat_sessions:
        _chat_sessions[sid] = {}
    _chat_sessions[sid][0] = StudentContext(
        student_id=sid, name=student.name,
        course=student.course, age=student.age,
        subject=data.subject,
    )

def _get_context(student, data):
    from backend.llm.socratic import StudentContext
    sid = student.id; cid = data.conversation_id or 0
    if sid not in _chat_sessions or cid not in _chat_sessions[sid]:
        _chat_sessions.setdefault(sid, {})[cid] = StudentContext(
            student_id=sid, name=student.name,
            course=student.course, age=student.age,
            subject=data.subject,
        )
    return _chat_sessions[sid][cid]

def _make_context(student):
    from backend.llm.socratic import StudentContext
    return StudentContext(
        student_id=student.id, name=student.name,
        course=student.course, age=student.age,
        subject="Programacion",
    )

def _save_msg(db, conv_id, role, content):
    msg = Message(conversation_id=conv_id, role=role, content=content)
    db.add(msg); db.commit()
