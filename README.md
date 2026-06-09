# 🎓 EduIA — Tutor de IA Local para Centros Educativos

> App de escritorio 100% local, sin internet, sin datos en la nube.  
> Cumple RGPD y LOPDGDD. Diseñada para alumnos de 12 a 20 años.

---

## ¿Qué es EduIA?

EduIA es una aplicación de escritorio que integra un modelo de IA local (sin conexión a internet) para asistir a alumnos y profesores en centros educativos españoles.

- **App Alumnos** (este repositorio) — Tutor socrático que guía sin dar respuestas directas
- **App Profesores** (repositorio privado) — Corrección asistida, rúbricas y libro de notas

---

## 🔒 Privacidad por diseño

- ✅ 100% local — ningún dato sale del dispositivo
- ✅ Sin cuenta, sin email, sin nube
- ✅ Cumple RGPD + LOPDGDD
- ✅ Apto para menores de edad
- ✅ Derecho al olvido: borrar carpeta = borrar todo

---

## 🖥️ Requisitos mínimos

| Componente | Mínimo |
|---|---|
| SO | Windows 10/11 (64 bits) |
| RAM | 4 GB |
| Almacenamiento | 3 GB libres |
| CPU | x64, 4 núcleos recomendado |
| Internet | No necesario (solo instalación inicial) |

---

## 📁 Estructura del proyecto

```
EduIA/
├── runtime/                  # Motor de IA empaquetado
│   ├── llama_cpp_binary/     # Binarios de llama.cpp por plataforma
│   └── models/               # Modelos GGUF
├── backend/                  # Servidor local Python/FastAPI
│   ├── llm/                  # Motor LLM y lógica socrática
│   ├── storage/              # SQLite local
│   ├── security/             # Autenticación local
│   ├── grading/              # Corrección asistida (profesores)
│   ├── file_generator/       # Generador de archivos .py .html etc
│   └── api/                  # Endpoints FastAPI
├── frontend/                 # Interfaz Tauri
│   ├── student/              # UI alumnos
│   └── teacher/              # UI profesores
├── scripts/                  # Utilidades y setup
├── docs/                     # Documentación
└── tests/                    # Tests automatizados
```

---

## 🚀 Instalación para desarrollo

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/EduIA.git
cd EduIA

# 2. Crear entorno virtual Python
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Descargar modelo (primera vez)
python scripts/download_model.py

# 5. Arrancar el backend
python backend/main.py
```

---

## 🧠 Modelos soportados

| Modelo | RAM necesaria | Calidad |
|---|---|---|
| Qwen2.5-1.5B-Instruct Q4_K_M | ~1.5 GB | ⭐⭐⭐ |
| Phi-3.5-mini Q4_K_M | ~2.5 GB | ⭐⭐⭐⭐ |
| Gemma-2-2B Q4_K_M | ~2 GB | ⭐⭐⭐⭐ |
| SmolLM2-1.7B Q4_K_M | ~1.2 GB | ⭐⭐ |

---

## 📄 Licencia

MIT License — Ver [LICENSE](LICENSE)

---

## 👥 Contribuir

Este proyecto está en fase inicial. Si eres profesor, pedagogo o desarrollador y quieres contribuir, abre un Issue.
