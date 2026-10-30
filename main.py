# main.py - Sistema de Asistencia (v2.0.1)

total_asistencias = 0

def registrar_asistencia(datos_alumno: dict):
    global total_asistencias

    # Hotfix: Validación estricta contra None o cadenas vacías
    dni_raw = datos_alumno.get("dni")
    if not dni_raw or not isinstance(dni_raw, str):
        print("[ERROR] El campo DNI es obligatorio y debe ser texto")
        return False

    dni = dni_raw.strip()
    materia = datos_alumno.get("materia", "Programación III")

    if len(dni) >= 7 and dni.isdigit():
        total_asistencias += 1
        print(f"[OK] Asistencia N°{total_asistencias} | DNI: {dni} | Materia: {materia}")
        return True

    print(f"[ERROR] Datos inválidos para DNI: {dni}")
    return False

if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v2.0.1 ===")
    registrar_asistencia({"dni": "40123456", "materia": "Programación III"})