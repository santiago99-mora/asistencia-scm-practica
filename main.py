# main.py - Sistema de Asistencia Integral (v3.0.0 - Compatible con v2.1.0)

import re
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import database

# =====================================================================
# SECCIÓN 1: LÓGICA BASE COMPATIBLE CON TESTS EXISTENTES (v2.1.0)
# =====================================================================

total_asistencias = 0
historial_registros: List[Dict[str, Any]] = []


def validar_dni(dni_raw: Any) -> Optional[str]:
    """
    Valida que el DNI sea una cadena numérica de al menos 7 dígitos.
    Devuelve el DNI limpio (sin espacios laterales) o None si es inválido.
    """
    if not dni_raw or not isinstance(dni_raw, str):
        return None
    dni = dni_raw.strip()
    if len(dni) >= 7 and dni.isdigit():
        return dni
    return None


def registrar_asistencia(datos_alumno: dict) -> bool:
    """
    Función base de registro en memoria (compatible con suite pytest v2.1.0).
    """
    global total_asistencias, historial_registros

    dni_raw = datos_alumno.get("dni")
    if not dni_raw or not isinstance(dni_raw, str):
        print("[ERROR] El campo DNI es obligatorio")
        return False

    dni = dni_raw.strip()
    materia = datos_alumno.get("materia", "Programación III")

    if len(dni) >= 7 and dni.isdigit():
        total_asistencias += 1
        registro = {"id": total_asistencias, "dni": dni, "materia": materia}
        historial_registros.append(registro)
        print(f"[OK] Asistencia N°{total_asistencias} | DNI: {dni} | Materia: {materia}")
        return True

    print(f"[ERROR] Datos inválidos para DNI: {dni}")
    return False


def obtener_reporte_estadistico() -> Dict[str, Any]:
    """
    Devuelve el reporte estadístico en memoria (compatible con suite pytest v2.1.0).
    """
    return {
        "total_asistencias": total_asistencias,
        "detalle": historial_registros,
    }


# =====================================================================
# SECCIÓN 2: MODELOS DE DATOS (PYDANTIC) Y UTILIDADES DE HORARIO
# =====================================================================

HORA_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
FECHA_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validar_formato_hora(hora: str) -> str:
    hora_limpia = (hora or "").strip()
    if not HORA_REGEX.match(hora_limpia):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El formato de hora debe ser HH:MM (00:00 a 23:59).",
        )
    return hora_limpia


def validar_formato_fecha(fecha_str: str) -> str:
    fecha_limpia = (fecha_str or "").strip()
    if not FECHA_REGEX.match(fecha_limpia):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El formato de fecha debe ser YYYY-MM-DD.",
        )
    try:
        datetime.strptime(fecha_limpia, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha ingresada no es una fecha calendario válida.",
        )
    return fecha_limpia


def calcular_estado_asistencia(
    hora_ingreso: Optional[str],
    horario_limite: str,
    estado_solicitado: Optional[str] = None,
    forzar_estado: bool = False,
) -> str:
    """
    Calcula el estado de asistencia ('presente', 'tardanza' o 'ausente').
    - Si estado_solicitado es 'ausente', registra 'ausente'.
    - Si forzar_estado es True y se indica un estado válido, respeta dicho estado.
    - Si se proporciona hora_ingreso (o el modo es automático), compara contra
      horario_limite: si hora_ingreso > horario_limite -> 'tardanza', sino 'presente'.
    """
    estado_norm = (estado_solicitado or "").strip().lower() or None

    if estado_norm not in (None, "auto", "presente", "tardanza", "ausente"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado debe ser 'presente', 'tardanza', 'ausente' o 'auto'.",
        )

    if estado_norm == "ausente":
        return "ausente"

    if forzar_estado and estado_norm in ("presente", "tardanza", "ausente"):
        return estado_norm

    if estado_norm == "tardanza":
        return "tardanza"

    # Si no se envió hora explícita y se pidió explícitamente 'presente', respetarlo
    if hora_ingreso is None and estado_norm == "presente":
        return "presente"

    hora_evaluar = validar_formato_hora(hora_ingreso or datetime.now().strftime("%H:%M"))
    limite_evaluar = validar_formato_hora(horario_limite)

    if hora_evaluar > limite_evaluar:
        return "tardanza"
    return "presente"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ConfiguracionUpdate(BaseModel):
    horario_limite: str = Field(..., description="Horario límite en formato HH:MM")
    materia_default: Optional[str] = Field(default="Programación III")


class AlumnoCreate(BaseModel):
    dni: str
    nombre: str
    apellido: str
    curso: str


class AlumnoUpdate(BaseModel):
    nombre: str
    apellido: str
    curso: str


class AsistenciaCreate(BaseModel):
    dni: str
    fecha: Optional[str] = None
    hora: Optional[str] = None
    estado: Optional[str] = None
    materia: Optional[str] = None
    observacion: Optional[str] = ""
    forzar_estado: bool = False


# =====================================================================
# SECCIÓN 3: APLICACIÓN FASTAPI Y AUTENTICACIÓN PROTEGIDA
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


# Inicializar base de datos al cargar el módulo para garantizar disponibilidad
database.init_db()

app = FastAPI(
    title="Sistema de Asistencia Académica",
    version="3.0.0",
    description="API REST para control de asistencia, gestión de alumnos y reportes con FastAPI y SQLite.",
    lifespan=lifespan,
)

security_scheme = HTTPBearer(auto_error=False)


def obtener_usuario_actual(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Dependencia de seguridad que protege las rutas de la API.
    Verifica que exista un Bearer token válido y activo en la base SQLite.
    """
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Debe iniciar sesión para acceder al sistema.",
        )

    token = credentials.credentials.strip()
    with database.get_db() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.nombre_completo, u.rol, s.created_at
            FROM sesiones s
            INNER JOIN usuarios u ON u.id = s.user_id
            WHERE s.token = ?;
            """,
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada. Por favor, inicie sesión nuevamente.",
        )

    return {
        "id": row["id"],
        "username": row["username"],
        "nombre_completo": row["nombre_completo"],
        "rol": row["rol"],
        "token": token,
    }


def obtener_configuracion_db(conn) -> Dict[str, str]:
    filas = conn.execute("SELECT clave, valor FROM configuracion;").fetchall()
    config = {fila["clave"]: fila["valor"] for fila in filas}
    return {
        "horario_limite": config.get("horario_limite", "08:15"),
        "materia_default": config.get("materia_default", "Programación III"),
    }


# =====================================================================
# SECCIÓN 4: ENDPOINTS DE AUTENTICACIÓN (LOGIN / LOGOUT / PERFIL)
# =====================================================================

@app.post("/api/auth/login")
def login(datos: LoginRequest):
    username = datos.username.strip()
    with database.get_db() as conn:
        usuario = conn.execute(
            "SELECT id, username, password_hash, nombre_completo, rol FROM usuarios WHERE username = ?;",
            (username,),
        ).fetchone()

        if not usuario or not database.verify_password(datos.password, usuario["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos.",
            )

        token = secrets.token_urlsafe(32)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO sesiones (token, user_id, created_at) VALUES (?, ?, ?);",
            (token, usuario["id"], ahora),
        )

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario["id"],
            "username": usuario["username"],
            "nombre_completo": usuario["nombre_completo"],
            "rol": usuario["rol"],
        },
    }


@app.post("/api/auth/logout")
def logout(usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual)):
    with database.get_db() as conn:
        conn.execute("DELETE FROM sesiones WHERE token = ?;", (usuario_actual["token"],))
    return {"mensaje": "Sesión cerrada correctamente."}


@app.get("/api/auth/me")
def perfil_usuario(usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual)):
    return {
        "id": usuario_actual["id"],
        "username": usuario_actual["username"],
        "nombre_completo": usuario_actual["nombre_completo"],
        "rol": usuario_actual["rol"],
    }


# =====================================================================
# SECCIÓN 5: ENDPOINTS DE CONFIGURACIÓN (HORARIO LÍMITE DE TARDANZA)
# =====================================================================

@app.get("/api/configuracion")
def obtener_configuracion(usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual)):
    with database.get_db() as conn:
        return obtener_configuracion_db(conn)


@app.put("/api/configuracion")
def actualizar_configuracion(
    datos: ConfiguracionUpdate,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    horario_validado = validar_formato_hora(datos.horario_limite)
    materia_limpia = (datos.materia_default or "Programación III").strip() or "Programación III"

    with database.get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('horario_limite', ?);",
            (horario_validado,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('materia_default', ?);",
            (materia_limpia,),
        )
        return {
            "mensaje": "Configuración actualizada correctamente.",
            "configuracion": obtener_configuracion_db(conn),
        }


# =====================================================================
# SECCIÓN 6: ENDPOINTS DE GESTIÓN DE ALUMNOS (CRUD COMPLETO)
# =====================================================================

@app.get("/api/alumnos")
def listar_alumnos(
    q: Optional[str] = Query(default=None, description="Filtro por DNI, nombre, apellido o curso"),
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    with database.get_db() as conn:
        if q and q.strip():
            patron = f"%{q.strip()}%"
            filas = conn.execute(
                """
                SELECT dni, nombre, apellido, curso, creado_en
                FROM alumnos
                WHERE dni LIKE ? OR nombre LIKE ? OR apellido LIKE ? OR curso LIKE ?
                ORDER BY apellido ASC, nombre ASC;
                """,
                (patron, patron, patron, patron),
            ).fetchall()
        else:
            filas = conn.execute(
                """
                SELECT dni, nombre, apellido, curso, creado_en
                FROM alumnos
                ORDER BY apellido ASC, nombre ASC;
                """
            ).fetchall()

    return [dict(fila) for fila in filas]


@app.get("/api/alumnos/{dni}")
def obtener_alumno(
    dni: str,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    dni_limpio = validar_dni(dni)
    if not dni_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El DNI debe ser numérico y tener al menos 7 dígitos.",
        )

    with database.get_db() as conn:
        fila = conn.execute(
            "SELECT dni, nombre, apellido, curso, creado_en FROM alumnos WHERE dni = ?;",
            (dni_limpio,),
        ).fetchone()

    if not fila:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe un alumno registrado con el DNI {dni_limpio}.",
        )
    return dict(fila)


@app.post("/api/alumnos", status_code=status.HTTP_201_CREATED)
def crear_alumno(
    datos: AlumnoCreate,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    dni_limpio = validar_dni(datos.dni)
    if not dni_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DNI inválido. Debe contener solo números y al menos 7 dígitos.",
        )

    nombre = datos.nombre.strip()
    apellido = datos.apellido.strip()
    curso = datos.curso.strip()

    if not nombre or not apellido or not curso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los campos nombre, apellido y curso son obligatorios.",
        )

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with database.get_db() as conn:
        existente = conn.execute(
            "SELECT dni FROM alumnos WHERE dni = ?;",
            (dni_limpio,),
        ).fetchone()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un alumno registrado con el DNI {dni_limpio}.",
            )

        conn.execute(
            """
            INSERT INTO alumnos (dni, nombre, apellido, curso, creado_en)
            VALUES (?, ?, ?, ?, ?);
            """,
            (dni_limpio, nombre, apellido, curso, ahora),
        )

    return {
        "mensaje": "Alumno creado correctamente.",
        "alumno": {
            "dni": dni_limpio,
            "nombre": nombre,
            "apellido": apellido,
            "curso": curso,
            "creado_en": ahora,
        },
    }


@app.put("/api/alumnos/{dni}")
def editar_alumno(
    dni: str,
    datos: AlumnoUpdate,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    dni_limpio = validar_dni(dni)
    if not dni_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DNI inválido. Debe contener solo números y al menos 7 dígitos.",
        )

    nombre = datos.nombre.strip()
    apellido = datos.apellido.strip()
    curso = datos.curso.strip()

    if not nombre or not apellido or not curso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los campos nombre, apellido y curso son obligatorios.",
        )

    with database.get_db() as conn:
        existente = conn.execute(
            "SELECT dni, creado_en FROM alumnos WHERE dni = ?;",
            (dni_limpio,),
        ).fetchone()
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el alumno con DNI {dni_limpio}.",
            )

        conn.execute(
            """
            UPDATE alumnos
            SET nombre = ?, apellido = ?, curso = ?
            WHERE dni = ?;
            """,
            (nombre, apellido, curso, dni_limpio),
        )

    return {
        "mensaje": "Alumno actualizado correctamente.",
        "alumno": {
            "dni": dni_limpio,
            "nombre": nombre,
            "apellido": apellido,
            "curso": curso,
            "creado_en": existente["creado_en"],
        },
    }


@app.delete("/api/alumnos/{dni}")
def eliminar_alumno(
    dni: str,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    dni_limpio = validar_dni(dni)
    if not dni_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DNI inválido.",
        )

    with database.get_db() as conn:
        existente = conn.execute(
            "SELECT dni, nombre, apellido FROM alumnos WHERE dni = ?;",
            (dni_limpio,),
        ).fetchone()
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el alumno con DNI {dni_limpio}.",
            )

        conn.execute("DELETE FROM alumnos WHERE dni = ?;", (dni_limpio,))

    return {
        "mensaje": f"Alumno {existente['apellido']}, {existente['nombre']} (DNI {dni_limpio}) eliminado correctamente.",
        "dni": dni_limpio,
    }


# =====================================================================
# SECCIÓN 7: ENDPOINTS DE REGISTRO Y CONSULTA DE ASISTENCIAS
# =====================================================================

@app.post("/api/asistencias", status_code=status.HTTP_201_CREATED)
def crear_asistencia(
    datos: AsistenciaCreate,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    dni_limpio = validar_dni(datos.dni)
    if not dni_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DNI inválido. Debe ser numérico y tener al menos 7 dígitos.",
        )

    fecha_registro = validar_formato_fecha(datos.fecha) if datos.fecha else date.today().strftime("%Y-%m-%d")
    hora_provista = validar_formato_hora(datos.hora) if datos.hora else None
    hora_efectiva = hora_provista or datetime.now().strftime("%H:%M")

    with database.get_db() as conn:
        alumno = conn.execute(
            "SELECT dni, nombre, apellido, curso FROM alumnos WHERE dni = ?;",
            (dni_limpio,),
        ).fetchone()
        if not alumno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El alumno con DNI {dni_limpio} no existe en el padrón.",
            )

        duplicado = conn.execute(
            "SELECT id, estado, hora FROM asistencias WHERE dni = ? AND fecha = ?;",
            (dni_limpio, fecha_registro),
        ).fetchone()
        if duplicado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"El alumno con DNI {dni_limpio} ya tiene asistencia registrada "
                    f"el día {fecha_registro} (Estado: {duplicado['estado']} a las {duplicado['hora']})."
                ),
            )

        config = obtener_configuracion_db(conn)
        horario_limite = config["horario_limite"]
        materia_final = (datos.materia or "").strip() or config["materia_default"]
        observacion_final = (datos.observacion or "").strip()

        estado_final = calcular_estado_asistencia(
            hora_ingreso=hora_provista,
            horario_limite=horario_limite,
            estado_solicitado=datos.estado,
            forzar_estado=datos.forzar_estado,
        )

        cursor = conn.execute(
            """
            INSERT INTO asistencias (dni, fecha, hora, estado, materia, observacion)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (dni_limpio, fecha_registro, hora_efectiva, estado_final, materia_final, observacion_final),
        )
        nuevo_id = cursor.lastrowid

    # Mantener sincronizado el registro estadístico en memoria (v2.1.0)
    registrar_asistencia({"dni": dni_limpio, "materia": materia_final})

    return {
        "mensaje": f"Asistencia registrada como '{estado_final.upper()}'.",
        "registro": {
            "id": nuevo_id,
            "dni": dni_limpio,
            "nombre": alumno["nombre"],
            "apellido": alumno["apellido"],
            "curso": alumno["curso"],
            "fecha": fecha_registro,
            "hora": hora_efectiva,
            "estado": estado_final,
            "materia": materia_final,
            "observacion": observacion_final,
            "horario_limite_aplicado": horario_limite,
        },
    }


@app.get("/api/asistencias")
def listar_asistencias_por_dia(
    fecha: Optional[str] = Query(default=None, description="Fecha en formato YYYY-MM-DD (o 'todas')"),
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    with database.get_db() as conn:
        config = obtener_configuracion_db(conn)

        if fecha and fecha.strip().lower() == "todas":
            fecha_consulta = "todas"
            filas = conn.execute(
                """
                SELECT a.id, a.dni, al.nombre, al.apellido, al.curso,
                       a.fecha, a.hora, a.estado, a.materia, a.observacion
                FROM asistencias a
                INNER JOIN alumnos al ON al.dni = a.dni
                ORDER BY a.fecha DESC, a.hora DESC, a.id DESC;
                """
            ).fetchall()
        else:
            fecha_consulta = validar_formato_fecha(fecha) if fecha else date.today().strftime("%Y-%m-%d")
            filas = conn.execute(
                """
                SELECT a.id, a.dni, al.nombre, al.apellido, al.curso,
                       a.fecha, a.hora, a.estado, a.materia, a.observacion
                FROM asistencias a
                INNER JOIN alumnos al ON al.dni = a.dni
                WHERE a.fecha = ?
                ORDER BY a.hora ASC, al.apellido ASC;
                """,
                (fecha_consulta,),
            ).fetchall()

    registros = [dict(f) for f in filas]
    presentes = sum(1 for r in registros if r["estado"] == "presente")
    tardanzas = sum(1 for r in registros if r["estado"] == "tardanza")
    ausentes = sum(1 for r in registros if r["estado"] == "ausente")

    return {
        "fecha": fecha_consulta,
        "horario_limite": config["horario_limite"],
        "resumen": {
            "total": len(registros),
            "presentes": presentes,
            "tardanzas": tardanzas,
            "ausentes": ausentes,
        },
        "registros": registros,
    }


@app.delete("/api/asistencias/{asistencia_id}")
def eliminar_asistencia(
    asistencia_id: int,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    with database.get_db() as conn:
        existente = conn.execute(
            "SELECT id, dni, fecha FROM asistencias WHERE id = ?;",
            (asistencia_id,),
        ).fetchone()
        if not existente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el registro de asistencia N°{asistencia_id}.",
            )
        conn.execute("DELETE FROM asistencias WHERE id = ?;", (asistencia_id,))

    return {
        "mensaje": "Registro de asistencia eliminado correctamente.",
        "id": asistencia_id,
    }


# =====================================================================
# SECCIÓN 8: ENDPOINTS DE INFORMES Y REPORTES POR ALUMNO
# =====================================================================

@app.get("/api/reportes/alumno/{dni}")
def reporte_por_alumno(
    dni: str,
    usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual),
):
    dni_limpio = validar_dni(dni)
    if not dni_limpio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DNI inválido. Debe contener solo números y al menos 7 dígitos.",
        )

    with database.get_db() as conn:
        alumno = conn.execute(
            "SELECT dni, nombre, apellido, curso, creado_en FROM alumnos WHERE dni = ?;",
            (dni_limpio,),
        ).fetchone()
        if not alumno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe un alumno registrado con el DNI {dni_limpio}.",
            )

        filas = conn.execute(
            """
            SELECT id, fecha, hora, estado, materia, observacion
            FROM asistencias
            WHERE dni = ?
            ORDER BY fecha DESC, id DESC;
            """,
            (dni_limpio,),
        ).fetchall()

    historial = [dict(f) for f in filas]
    total = len(historial)
    presentes = sum(1 for r in historial if r["estado"] == "presente")
    tardanzas = sum(1 for r in historial if r["estado"] == "tardanza")
    ausentes = sum(1 for r in historial if r["estado"] == "ausente")

    if total > 0:
        porcentaje_presentes = round((presentes / total) * 100, 2)
        porcentaje_tardanzas = round((tardanzas / total) * 100, 2)
        porcentaje_ausentes = round((ausentes / total) * 100, 2)
    else:
        porcentaje_presentes = 0.0
        porcentaje_tardanzas = 0.0
        porcentaje_ausentes = 0.0

    return {
        "alumno": dict(alumno),
        "estadisticas": {
            "total_registros": total,
            "presentes": presentes,
            "tardanzas": tardanzas,
            "ausentes": ausentes,
            "porcentaje_presentes": porcentaje_presentes,
            "porcentaje_tardanzas": porcentaje_tardanzas,
            "porcentaje_ausentes": porcentaje_ausentes,
        },
        "historial": historial,
    }


@app.get("/api/reportes/general")
def reporte_general(usuario_actual: Dict[str, Any] = Depends(obtener_usuario_actual)):
    hoy = date.today().strftime("%Y-%m-%d")
    with database.get_db() as conn:
        total_alumnos = conn.execute("SELECT COUNT(*) AS c FROM alumnos;").fetchone()["c"]
        filas_hoy = conn.execute(
            "SELECT estado FROM asistencias WHERE fecha = ?;",
            (hoy,),
        ).fetchall()
        filas_totales = conn.execute("SELECT estado FROM asistencias;").fetchall()
        config = obtener_configuracion_db(conn)

    total_global = len(filas_totales)
    pres_global = sum(1 for r in filas_totales if r["estado"] == "presente")
    tard_global = sum(1 for r in filas_totales if r["estado"] == "tardanza")
    aus_global = sum(1 for r in filas_totales if r["estado"] == "ausente")

    return {
        "fecha_actual": hoy,
        "horario_limite": config["horario_limite"],
        "total_alumnos_padron": total_alumnos,
        "hoy": {
            "registrados": len(filas_hoy),
            "presentes": sum(1 for r in filas_hoy if r["estado"] == "presente"),
            "tardanzas": sum(1 for r in filas_hoy if r["estado"] == "tardanza"),
            "ausentes": sum(1 for r in filas_hoy if r["estado"] == "ausente"),
        },
        "historico_global": {
            "total_registros": total_global,
            "presentes": pres_global,
            "tardanzas": tard_global,
            "ausentes": aus_global,
        },
    }


# =====================================================================
# SECCIÓN 9: ARCHIVOS ESTÁTICOS Y FRONTEND WEB
# =====================================================================

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def servir_frontend():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"mensaje": "Sistema de Asistencia API activa. Visite /docs para la documentación."}


if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v2.1.0 ===")
    registrar_asistencia({"dni": "40123456", "materia": "Programación III"})
    print("Reporte:", obtener_reporte_estadistico())
