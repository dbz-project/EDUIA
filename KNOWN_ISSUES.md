
---

### ISSUE-011

**Problema**

Permisos de escritura en directorios protegidos de Windows.

**Impacto**

La app arranca pero no puede guardar portfolio, logs o SQLite.

**Workaround**

Verificar que `database.db`, `logs/` y portfolio se crean en AppData del usuario, no en carpetas del sistema.

**Prioridad**

Alta — verificar en segundo equipo.

---

### ISSUE-012

**Problema**

Caracteres especiales en nombres de usuario o archivos.

**Impacto**

Fallos silenciosos al guardar o recuperar archivos.

**Ejemplos críticos**

- Usuario: `José`, `María García`
- Archivo: `Programación_Básica.py`

**Workaround**

El sanitizador de nombres ya filtra caracteres no seguros. Verificar en segundo equipo con nombre con tilde.

**Prioridad**

Media.

---

### ISSUE-013

**Problema**

Arranque múltiple accidental — doble clic en el acceso directo.

**Impacto**

Dos instancias del backend intentan usar el puerto 8765. El segundo falla silenciosamente.

**Workaround**

`main.rs` verifica `health check` antes de lanzar el backend. Si ya responde, no lanza otro proceso.

**Prioridad**

Media-Alta — ya mitigado en main.rs v5.
