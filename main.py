# main.py - Sistema de Asistencia (v2.1.0)

total_asistencias = 0
historial_registros = []

def registrar_asistencia(datos_alumno: dict):
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

# NUEVA FUNCIONALIDAD (Compatible hacia atrás)
def obtener_reporte_estadistico():
    return {
        "total_asistencias": total_asistencias,
        "detalle": historial_registros
    }

if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v2.1.0 ===")
    registrar_asistencia({"dni": "40123456", "materia": "Programación III"})
    print("Reporte:", obtener_reporte_estadistico())