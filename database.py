# database.py - Capa de Persistencia SQLite y Seguridad (PBKDF2-HMAC-SHA256)

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("ASISTENCIA_DB_PATH", str(BASE_DIR / "asistencia.db"))

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """
    Genera un hash seguro de contraseña usando PBKDF2-HMAC-SHA256 con sal aleatoria.
    Nunca almacena contraseñas en texto plano.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("La contraseña no puede estar vacía")
    salt = secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${derived_key}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verifica una contraseña en texto plano contra el hash PBKDF2 almacenado
    utilizando comparación en tiempo constante (hmac.compare_digest).
    """
    try:
        algorithm, iterations_str, salt, expected_hash = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(computed_hash, expected_hash)
    except (ValueError, AttributeError, TypeError):
        return False


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Crea y configura una conexión a SQLite con soporte para claves foráneas."""
    target_path = db_path or DB_PATH
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager que gestiona transacciones y cierre seguro de conexión."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """
    Crea automáticamente las tablas necesarias en SQLite e inserta el usuario
    docente de ejemplo, la configuración del horario límite y alumnos de prueba.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nombre_completo TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'docente'
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sesiones (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alumnos (
                dni TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                curso TEXT NOT NULL,
                creado_en TEXT NOT NULL
            );
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS asistencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dni TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                estado TEXT NOT NULL CHECK(estado IN ('presente', 'tardanza', 'ausente')),
                materia TEXT NOT NULL DEFAULT 'Programación III',
                observacion TEXT NOT NULL DEFAULT '',
                UNIQUE(dni, fecha),
                FOREIGN KEY (dni) REFERENCES alumnos(dni) ON DELETE CASCADE
            );
            """
        )

        # Configuración por defecto (horario límite para cálculo de tardanza)
        cursor.execute(
            "INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?);",
            ("horario_limite", "08:15"),
        )
        cursor.execute(
            "INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?);",
            ("materia_default", "Programación III"),
        )

        # Usuario de ejemplo (docente / docente123) con contraseña hasheada
        cursor.execute("SELECT COUNT(*) AS total FROM usuarios;")
        if cursor.fetchone()["total"] == 0:
            cursor.execute(
                """
                INSERT INTO usuarios (username, password_hash, nombre_completo, rol)
                VALUES (?, ?, ?, ?);
                """,
                (
                    "docente",
                    hash_password("docente123"),
                    "Prof. Docente Titular",
                    "docente",
                ),
            )

        # Alumnos de ejemplo y registros históricos iniciales
        cursor.execute("SELECT COUNT(*) AS total FROM alumnos;")
        if cursor.fetchone()["total"] == 0:
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alumnos_ejemplo = [
                ("40123456", "Martín", "Gómez", "3° Año - Comisión A", ahora),
                ("38999111", "Lucía", "Fernández", "3° Año - Comisión A", ahora),
                ("41222333", "Santiago", "Rodríguez", "3° Año - Comisión B", ahora),
                ("42555666", "Valentina", "López", "3° Año - Comisión A", ahora),
                ("39876543", "Mateo", "Pérez", "3° Año - Comisión B", ahora),
            ]
            cursor.executemany(
                """
                INSERT INTO alumnos (dni, nombre, apellido, curso, creado_en)
                VALUES (?, ?, ?, ?, ?);
                """,
                alumnos_ejemplo,
            )

            asistencias_ejemplo = [
                ("40123456", "2026-11-02", "08:05", "presente", "Programación III", "Ingreso puntual"),
                ("40123456", "2026-11-03", "08:28", "tardanza", "Programación III", "Ingreso posterior al límite"),
                ("40123456", "2026-11-04", "08:00", "presente", "Programación III", "Ingreso puntual"),
                ("40123456", "2026-11-05", "08:10", "presente", "Programación III", "Ingreso puntual"),
                ("38999111", "2026-11-02", "08:02", "presente", "Programación III", "Ingreso puntual"),
                ("38999111", "2026-11-03", "08:12", "presente", "Programación III", "Ingreso puntual"),
                ("38999111", "2026-11-04", "09:00", "ausente", "Programación III", "Falta sin aviso"),
                ("41222333", "2026-11-02", "08:25", "tardanza", "Práctica Profesional II", "Demora en transporte"),
                ("41222333", "2026-11-03", "08:04", "presente", "Práctica Profesional II", "Ingreso puntual"),
                ("42555666", "2026-11-02", "08:00", "presente", "Programación III", "Ingreso puntual"),
                ("39876543", "2026-11-02", "08:35", "ausente", "Práctica Profesional II", "Certificado médico"),
            ]
            cursor.executemany(
                """
                INSERT INTO asistencias (dni, fecha, hora, estado, materia, observacion)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                asistencias_ejemplo,
            )
