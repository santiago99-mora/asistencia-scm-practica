# Sistema de Asistencia Académica (FastAPI + SQLite)

Sistema integral de control de asistencia con autenticación protegida, cálculo automático de tardanzas según horario límite configurable, gestión ABM (CRUD) de alumnos, consulta diaria e informes estadísticos por alumno.

## Credenciales de Ejemplo

- **Usuario:** `docente`
- **Contraseña:** `docente123`

*(La contraseña se almacena hasheada con `PBKDF2-HMAC-SHA256` y sal criptográfica aleatoria en SQLite, nunca en texto plano).*

## Instalación y Ejecución

```bash
# 1. Crear y activar entorno virtual (opcional pero recomendado)
python -m venv venv
# En Linux / macOS / WSL:
source venv/bin/activate
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar el servidor con Uvicorn
uvicorn main:app --reload
```

Abrir en el navegador: **http://127.0.0.1:8000**

## Ejecución de Tests

```bash
pytest -v
```
