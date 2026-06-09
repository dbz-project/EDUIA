"""
backend/security/auth.py
Autenticación 100% local. Sin tokens externos, sin JWT en la nube.
PIN para alumnos (simple), contraseña para profesores (más robusta).
"""

import bcrypt
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.storage.db import Student, Teacher

logger = logging.getLogger(__name__)

# Sesiones activas en memoria (se limpian al cerrar la app)
# { token: {"user_id": int, "role": "student"|"teacher", "expires": datetime} }
_active_sessions: dict = {}

SESSION_DURATION_HOURS = 8  # Duración de sesión por día escolar


class AuthService:
    """Gestión de autenticación local."""

    # ── ALUMNOS ────────────────────────────────────────────

    def create_student(
        self, db: Session, name: str, pin: str, course: str, age: int
    ) -> Student:
        """
        Crea un perfil de alumno con PIN hasheado.
        El PIN es solo numérico (4 dígitos) para que sea fácil para el alumno.
        """
        if len(pin) < 4:
            raise ValueError("El PIN debe tener al menos 4 dígitos")
        
        pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
        
        student = Student(
            name=name,
            pin_hash=pin_hash,
            course=course,
            age=age,
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        
        logger.info(f"Alumno creado: {name} ({course})")
        return student

    def login_student(self, db: Session, name: str, pin: str) -> Optional[str]:
        """
        Login de alumno con nombre + PIN.
        Retorna token de sesión local o None si falla.
        """
        student = db.query(Student).filter(
            Student.name == name,
            Student.is_active == True
        ).first()
        
        if not student:
            logger.warning(f"Intento de login fallido: alumno '{name}' no encontrado")
            return None
        
        if not bcrypt.checkpw(pin.encode(), student.pin_hash.encode()):
            logger.warning(f"PIN incorrecto para alumno: {name}")
            return None
        
        # Actualizar último login
        student.last_login = datetime.now()
        db.commit()
        
        token = self._create_session(student.id, "student")
        logger.info(f"Login correcto: alumno {name}")
        return token

    # ── PROFESORES ─────────────────────────────────────────

    def create_teacher(
        self, db: Session, name: str, password: str, subject: str = ""
    ) -> Teacher:
        """Crea perfil de profesor con contraseña hasheada."""
        if len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        teacher = Teacher(
            name=name,
            password_hash=password_hash,
            subject=subject,
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        
        logger.info(f"Profesor creado: {name}")
        return teacher

    def login_teacher(self, db: Session, name: str, password: str) -> Optional[str]:
        """Login de profesor. Retorna token de sesión o None."""
        teacher = db.query(Teacher).filter(
            Teacher.name == name,
            Teacher.is_active == True
        ).first()
        
        if not teacher:
            return None
        
        if not bcrypt.checkpw(password.encode(), teacher.password_hash.encode()):
            logger.warning(f"Contraseña incorrecta para profesor: {name}")
            return None
        
        teacher.last_login = datetime.now()
        db.commit()
        
        token = self._create_session(teacher.id, "teacher")
        logger.info(f"Login correcto: profesor {name}")
        return token

    # ── SESIONES ───────────────────────────────────────────

    def _create_session(self, user_id: int, role: str) -> str:
        """Crea sesión local en memoria."""
        token = secrets.token_hex(32)
        _active_sessions[token] = {
            "user_id": user_id,
            "role": role,
            "expires": datetime.now() + timedelta(hours=SESSION_DURATION_HOURS),
        }
        return token

    def validate_session(self, token: str) -> Optional[dict]:
        """
        Valida token de sesión.
        Retorna info de sesión o None si inválido/expirado.
        """
        session = _active_sessions.get(token)
        if not session:
            return None
        
        if datetime.now() > session["expires"]:
            del _active_sessions[token]
            return None
        
        return session

    def logout(self, token: str):
        """Cierra sesión eliminando el token."""
        if token in _active_sessions:
            del _active_sessions[token]

    def get_current_student(self, db: Session, token: str) -> Optional[Student]:
        """Helper para obtener el alumno actual desde el token."""
        session = self.validate_session(token)
        if not session or session["role"] != "student":
            return None
        return db.query(Student).filter(Student.id == session["user_id"]).first()

    def get_current_teacher(self, db: Session, token: str) -> Optional[Teacher]:
        """Helper para obtener el profesor actual desde el token."""
        session = self.validate_session(token)
        if not session or session["role"] != "teacher":
            return None
        return db.query(Teacher).filter(Teacher.id == session["user_id"]).first()


# Instancia global
auth_service = AuthService()
