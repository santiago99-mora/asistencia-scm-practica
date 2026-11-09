import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient

import database
import main
from main import app, registrar_asistencia, obtener_reporte_estadistico


# =====================================================================
# 1. TESTS ORIGINALES (v2.1.0 - CONSERVADOS ÍNTEGRAMENTE)
# =====================================================================

@pytest.fixture(autouse=True)
def limpiar_estado():
    """
    Fixture que limpia y restablece las variables globales de estado 
    antes de cada ejecución de prueba para asegurar el aislamiento.
    """
    main.total_asistencias = 0
    main.historial_registros.clear()
    yield


def test_registrar_asistencia_exitoso():
    """Verifica que una asistencia con DNI válido se registre correctamente."""
    alumno = {"dni": "40123456", "materia": "Programación III"}
    resultado = registrar_asistencia(alumno)
    
    assert resultado is True
    assert main.total_asistencias == 1
    assert len(main.historial_registros) == 1
    assert main.historial_registros[0]["dni"] == "40123456"
    assert main.historial_registros[0]["materia"] == "Programación III"


def test_registrar_asistencia_materia_personalizada():
    """Verifica que se registre con una materia específica."""
    alumno = {"dni": "38999111", "materia": "Práctica Profesional II"}
    resultado = registrar_asistencia(alumno)
    
    assert resultado is True
    assert main.historial_registros[0]["materia"] == "Práctica Profesional II"


def test_registrar_asistencia_dni_invalido_corto():
    """Verifica que se rechace un DNI con menos de 7 dígitos."""
    alumno = {"dni": "123", "materia": "Programación III"}
    resultado = registrar_asistencia(alumno)
    
    assert resultado is False
    assert main.total_asistencias == 0
    assert len(main.historial_registros) == 0


def test_registrar_asistencia_dni_con_letras():
    """Verifica que un DNI con caracteres no numéricos sea rechazado."""
    alumno = {"dni": "40123ABC", "materia": "Programación III"}
    resultado = registrar_asistencia(alumno)
    
    assert resultado is False
    assert main.total_asistencias == 0


def test_registrar_asistencia_sin_dni():
    """Verifica el manejo cuando no existe el campo DNI."""
    alumno = {"materia": "Programación III"}
    resultado = registrar_asistencia(alumno)
    
    assert resultado is False
    assert main.total_asistencias == 0


def test_obtener_reporte_estadistico():
    """Verifica que el reporte devuelva el total y detalle correctos."""
    registrar_asistencia({"dni": "40123456", "materia": "Programación III"})
    registrar_asistencia({"dni": "41222333", "materia": "Práctica Profesional II"})
    
    reporte = obtener_reporte_estadistico()
    
    assert reporte["total_asistencias"] == 2
    assert len(reporte["detalle"]) == 2
    assert reporte["detalle"][0]["dni"] == "40123456"
    assert reporte["detalle"][1]["dni"] == "41222333"


# =====================================================================
# 2. TESTS INTEGRALES DEL SISTEMA WEB (FASTAPI + SQLITE + AUTH)
# =====================================================================

@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Configura una base SQLite temporal aislada por test y devuelve TestClient."""
    db_temporal = str(tmp_path / "test_asistencia.db")
    monkeypatch.setattr(database, "DB_PATH", db_temporal)
    database.init_db(db_temporal)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def auth_headers(api_client):
    """Inicia sesión con el usuario docente de ejemplo y devuelve headers Bearer."""
    resp = api_client.post(
        "/api/auth/login",
        json={"username": "docente", "password": "docente123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_no_texto_plano(api_client):
    """Verifica que la contraseña en SQLite esté hasheada con PBKDF2 y nunca en texto plano."""
    with database.get_db() as conn:
        fila = conn.execute(
            "SELECT password_hash FROM usuarios WHERE username = 'docente';"
        ).fetchone()

    assert fila is not None
    stored_hash = fila["password_hash"]
    assert stored_hash != "docente123"
    assert "docente123" not in stored_hash
    assert stored_hash.startswith("pbkdf2_sha256$")
    assert database.verify_password("docente123", stored_hash) is True
    assert database.verify_password("clave_incorrecta", stored_hash) is False


def test_rutas_protegidas_sin_login(api_client):
    """Verifica que ninguna ruta protegida pueda usarse sin iniciar sesión."""
    assert api_client.get("/api/alumnos").status_code == 401
    assert api_client.post(
        "/api/alumnos",
        json={"dni": "44111222", "nombre": "Ana", "apellido": "Paz", "curso": "1° A"},
    ).status_code == 401
    assert api_client.post(
        "/api/asistencias",
        json={"dni": "40123456"},
    ).status_code == 401
    assert api_client.get("/api/asistencias").status_code == 401
    assert api_client.get("/api/reportes/alumno/40123456").status_code == 401
    assert api_client.get("/api/configuracion").status_code == 401
    assert api_client.put(
        "/api/configuracion",
        json={"horario_limite": "09:00"},
    ).status_code == 401


def test_login_exitoso_fallido_y_logout(api_client):
    """Prueba login inválido, login válido, consulta de perfil y cierre de sesión."""
    fallido = api_client.post(
        "/api/auth/login",
        json={"username": "docente", "password": "mal_password"},
    )
    assert fallido.status_code == 401

    exitoso = api_client.post(
        "/api/auth/login",
        json={"username": "docente", "password": "docente123"},
    )
    assert exitoso.status_code == 200
    token = exitoso.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    perfil = api_client.get("/api/auth/me", headers=headers)
    assert perfil.status_code == 200
    assert perfil.json()["username"] == "docente"

    cierre = api_client.post("/api/auth/logout", headers=headers)
    assert cierre.status_code == 200

    # Tras cerrar sesión, el token queda invalidado
    post_logout = api_client.get("/api/auth/me", headers=headers)
    assert post_logout.status_code == 401


def test_crud_completo_alumnos(api_client, auth_headers):
    """Verifica agregar, listar, filtrar, editar y borrar alumnos con validación de DNI."""
    # DNI inválido
    invalido = api_client.post(
        "/api/alumnos",
        headers=auth_headers,
        json={"dni": "12AB", "nombre": "Juan", "apellido": "Díaz", "curso": "2° A"},
    )
    assert invalido.status_code == 400

    # Crear alumno válido
    creado = api_client.post(
        "/api/alumnos",
        headers=auth_headers,
        json={"dni": "45123789", "nombre": "Camila", "apellido": "Sosa", "curso": "3° Año - Comisión C"},
    )
    assert creado.status_code == 201
    assert creado.json()["alumno"]["dni"] == "45123789"

    # Rechazar DNI duplicado
    duplicado = api_client.post(
        "/api/alumnos",
        headers=auth_headers,
        json={"dni": "45123789", "nombre": "Camila", "apellido": "Sosa", "curso": "3° Año - Comisión C"},
    )
    assert duplicado.status_code == 409

    # Editar alumno
    editado = api_client.put(
        "/api/alumnos/45123789",
        headers=auth_headers,
        json={"nombre": "Camila Belén", "apellido": "Sosa", "curso": "4° Año - Comisión A"},
    )
    assert editado.status_code == 200
    assert editado.json()["alumno"]["nombre"] == "Camila Belén"
    assert editado.json()["alumno"]["curso"] == "4° Año - Comisión A"

    # Buscar alumno
    busqueda = api_client.get("/api/alumnos?q=45123789", headers=auth_headers)
    assert busqueda.status_code == 200
    assert len(busqueda.json()) == 1

    # Borrar alumno
    borrado = api_client.delete("/api/alumnos/45123789", headers=auth_headers)
    assert borrado.status_code == 200

    no_encontrado = api_client.get("/api/alumnos/45123789", headers=auth_headers)
    assert no_encontrado.status_code == 404


def test_registro_asistencia_validaciones_y_duplicado_mismo_dia(api_client, auth_headers):
    """Valida DNI, existencia del alumno y bloqueo de doble registro en la misma fecha."""
    # DNI inválido
    resp_dni_mal = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "999", "fecha": "2026-11-10", "hora": "08:00"},
    )
    assert resp_dni_mal.status_code == 400

    # Alumno inexistente
    resp_inexistente = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "99999999", "fecha": "2026-11-10", "hora": "08:00"},
    )
    assert resp_inexistente.status_code == 404

    # Primer registro del día -> OK
    primer_registro = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "40123456", "fecha": "2026-11-10", "hora": "08:05"},
    )
    assert primer_registro.status_code == 201
    assert primer_registro.json()["registro"]["estado"] == "presente"

    # Segundo registro el mismo día para el mismo alumno -> Rechazado (409)
    segundo_registro = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "40123456", "fecha": "2026-11-10", "hora": "08:10"},
    )
    assert segundo_registro.status_code == 409


def test_calculo_tardanza_cambio_horario_limite_y_ausente(api_client, auth_headers):
    """Verifica cálculo automático de presente/tardanza según horario límite modificable y estado ausente."""
    # Horario límite inicial es 08:15 -> 08:25 debe ser tardanza
    tarde = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "40123456", "fecha": "2026-11-11", "hora": "08:25"},
    )
    assert tarde.status_code == 201
    assert tarde.json()["registro"]["estado"] == "tardanza"

    # Cambiar horario límite a 09:00
    cambio = api_client.put(
        "/api/configuracion",
        headers=auth_headers,
        json={"horario_limite": "09:00", "materia_default": "Programación III"},
    )
    assert cambio.status_code == 200
    assert cambio.json()["configuracion"]["horario_limite"] == "09:00"

    # Ahora 08:45 debe calcularse como presente
    puntual = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "38999111", "fecha": "2026-11-11", "hora": "08:45"},
    )
    assert puntual.status_code == 201
    assert puntual.json()["registro"]["estado"] == "presente"

    # Registrar ausente explícitamente
    ausente = api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "41222333", "fecha": "2026-11-11", "hora": "09:10", "estado": "ausente"},
    )
    assert ausente.status_code == 201
    assert ausente.json()["registro"]["estado"] == "ausente"

    # Consultar asistencias del día 2026-11-11
    del_dia = api_client.get("/api/asistencias?fecha=2026-11-11", headers=auth_headers)
    assert del_dia.status_code == 200
    resumen = del_dia.json()["resumen"]
    assert resumen["total"] == 3
    assert resumen["presentes"] == 1
    assert resumen["tardanzas"] == 1
    assert resumen["ausentes"] == 1


def test_reporte_por_alumno_con_porcentajes(api_client, auth_headers):
    """Verifica el informe por DNI con conteos exactos y porcentajes de presentes, tardanzas y ausencias."""
    api_client.post(
        "/api/alumnos",
        headers=auth_headers,
        json={"dni": "46000111", "nombre": "Sofía", "apellido": "Méndez", "curso": "3° A"},
    )

    # 2 presentes (50%), 1 tardanza (25%), 1 ausente (25%) -> Total 4 registros
    api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "46000111", "fecha": "2026-11-01", "hora": "08:00"},
    )
    api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "46000111", "fecha": "2026-11-02", "hora": "08:10"},
    )
    api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "46000111", "fecha": "2026-11-03", "hora": "08:40"},
    )
    api_client.post(
        "/api/asistencias",
        headers=auth_headers,
        json={"dni": "46000111", "fecha": "2026-11-04", "hora": "08:00", "estado": "ausente"},
    )

    rep = api_client.get("/api/reportes/alumno/46000111", headers=auth_headers)
    assert rep.status_code == 200
    datos = rep.json()

    assert datos["alumno"]["dni"] == "46000111"
    est = datos["estadisticas"]
    assert est["total_registros"] == 4
    assert est["presentes"] == 2
    assert est["tardanzas"] == 1
    assert est["ausentes"] == 1
    assert est["porcentaje_presentes"] == 50.0
    assert est["porcentaje_tardanzas"] == 25.0
    assert est["porcentaje_ausentes"] == 25.0
    assert len(datos["historial"]) == 4


def test_frontend_estatico_disponible(api_client):
    """Verifica que el HTML, CSS y JS del frontend se sirvan correctamente."""
    res_html = api_client.get("/")
    assert res_html.status_code == 200
    assert "Sistema de Asistencia" in res_html.text

    res_css = api_client.get("/static/styles.css")
    assert res_css.status_code == 200

    res_js = api_client.get("/static/app.js")
    assert res_js.status_code == 200
