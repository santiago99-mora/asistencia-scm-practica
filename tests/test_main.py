import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import main
from main import registrar_asistencia, obtener_reporte_estadistico

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