# main.py - Sistema de Asistencia (v1.1.0)
total_asistencias = 0

def registrar_asistencia(dni: str):
    global total_asistencias
    dni_limpio = dni.strip()
    if len(dni_limpio) >= 7 and dni_limpio.isdigit():
        total_asistencias += 1
        print(f"[OK] Asistencia N°{total_asistencias} para DNI: {dni_limpio}")
        return True
    print("[ERROR] DNI invalido")
    return False

if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v1.1.0 ===")
    registrar_asistencia("40123456")
    registrar_asistencia("38999111")
    print(f"Total procesados en sesion: {total_asistencias}")