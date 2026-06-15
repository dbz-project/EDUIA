"""
backend/storage/db.py
Base de datos SQLite local.
Un único archivo .db en el PC del usuario. Sin servidor. Sin cloud.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, 
    DateTime, Text, Float, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE BASE DE DATOS
# ─────────────────────────────────────────────

def get_db_path() -> str:
    """
    Ruta del archivo .db — en la carpeta de datos del usuario.
    Windows: C:\\Users\\[usuario]\\AppData\\Local\\EduIA\\eduia.db
    """
    if os.name == "nt":  # Windows
        app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        db_dir = Path(app_data) / "EduIA"
    else:
        db_dir = Path.home() / ".local" / "share" / "EduIA"
    
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "eduia.db")


DB_PATH = get_db_path()
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine_db = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_db)
Base = declarative_base()


# ─────────────────────────────────────────────
# MODELOS DE BASE DE DATOS
# ─────────────────────────────────────────────

class Student(Base):
    """Perfil del alumno. Sin email, sin datos sensibles innecesarios."""
    __tablename__ = "students"
    
    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    pin_hash    = Column(String(200), nullable=False)  # PIN hasheado con bcrypt
    course      = Column(String(20), nullable=False)   # "1ESO", "2ESO", etc.
    age         = Column(Integer, nullable=False)
    created_at  = Column(DateTime, default=datetime.now)
    last_login  = Column(DateTime, nullable=True)
    is_active   = Column(Boolean, default=True)
    
    # Relaciones
    conversations = relationship("Conversation", back_populates="student")
    portfolio     = relationship("PortfolioItem", back_populates="student")


class Teacher(Base):
    """Perfil del profesor."""
    __tablename__ = "teachers"
    
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)
    password_hash = Column(String(200), nullable=False)
    subject       = Column(String(100), nullable=True)  # Asignatura principal
    created_at    = Column(DateTime, default=datetime.now)
    last_login    = Column(DateTime, nullable=True)
    is_active     = Column(Boolean, default=True)
    
    # Relaciones
    rubrics  = relationship("Rubric", back_populates="teacher")
    criteria = relationship("GradingCriteria", back_populates="teacher")


class Conversation(Base):
    """
    Historial de conversaciones alumno-IA.
    Guardado localmente para el portfolio del alumno.
    """
    __tablename__ = "conversations"
    
    id           = Column(Integer, primary_key=True, index=True)
    student_id   = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject      = Column(String(100), nullable=False)
    topic        = Column(String(200), nullable=True)   # Tema de la conversación
    started_at   = Column(DateTime, default=datetime.now)
    ended_at     = Column(DateTime, nullable=True)
    hints_used   = Column(Integer, default=0)
    
    student  = relationship("Student", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Mensaje individual en una conversación."""
    __tablename__ = "messages"
    
    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role            = Column(String(20), nullable=False)   # "user" o "assistant"
    content         = Column(Text, nullable=False)
    created_at      = Column(DateTime, default=datetime.now)
    hint_level      = Column(Integer, default=0)
    
    conversation = relationship("Conversation", back_populates="messages")


class PortfolioItem(Base):
    """
    Archivo generado por el alumno con ayuda de la IA.
    Se guarda en el portfolio local del alumno.
    """
    __tablename__ = "portfolio_items"
    
    id           = Column(Integer, primary_key=True, index=True)
    student_id   = Column(Integer, ForeignKey("students.id"), nullable=False)
    filename     = Column(String(200), nullable=False)
    file_type    = Column(String(20), nullable=False)    # "py", "html", "md", etc.
    file_path    = Column(String(500), nullable=False)   # Ruta local del archivo
    subject      = Column(String(100), nullable=False)
    topic        = Column(String(200), nullable=True)
    eval_passed  = Column(Boolean, default=False)        # ¿Pasó la evaluación previa?
    hints_needed = Column(Integer, default=0)
    created_at   = Column(DateTime, default=datetime.now)
    
    student = relationship("Student", back_populates="portfolio")


class Rubric(Base):
    """Rúbrica subida por el profesor para evaluar trabajos."""
    __tablename__ = "rubrics"
    
    id          = Column(Integer, primary_key=True, index=True)
    teacher_id  = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    name        = Column(String(200), nullable=False)
    subject     = Column(String(100), nullable=False)
    content     = Column(Text, nullable=False)           # Contenido de la rúbrica
    file_path   = Column(String(500), nullable=True)     # PDF/DOCX original
    created_at  = Column(DateTime, default=datetime.now)
    
    teacher = relationship("Teacher", back_populates="rubrics")


class GradingCriteria(Base):
    """Criterios de calificación de la asignatura."""
    __tablename__ = "grading_criteria"
    
    id          = Column(Integer, primary_key=True, index=True)
    teacher_id  = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject     = Column(String(100), nullable=False)
    course      = Column(String(20), nullable=False)
    criteria    = Column(Text, nullable=False)            # JSON con criterios y pesos
    created_at  = Column(DateTime, default=datetime.now)
    
    teacher = relationship("Teacher", back_populates="criteria")


class Grade(Base):
    """Nota de un alumno en una actividad/evaluación."""
    __tablename__ = "grades"
    
    id           = Column(Integer, primary_key=True, index=True)
    student_id   = Column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id   = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject      = Column(String(100), nullable=False)
    course       = Column(String(20), nullable=False)
    trimester    = Column(Integer, nullable=False)         # 1, 2 o 3
    activity     = Column(String(200), nullable=False)    # Nombre de la actividad
    grade_value  = Column(Float, nullable=False)          # 0.0 - 10.0
    weight       = Column(Float, default=1.0)             # Peso en la nota final
    notes        = Column(Text, nullable=True)            # Observaciones del profesor
    ai_suggested = Column(Float, nullable=True)           # Nota sugerida por la IA
    created_at   = Column(DateTime, default=datetime.now)


# ─────────────────────────────────────────────
# INICIALIZACIÓN
# ─────────────────────────────────────────────

def init_db():
    """Crea todas las tablas si no existen. Se llama al arrancar la app."""
    Base.metadata.create_all(bind=engine_db)
    logger.info(f"[OK] Base de datos inicializada en: {DB_PATH}")


def get_db() -> Session:
    """
    Dependencia FastAPI para obtener sesión de base de datos.
    Uso: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
