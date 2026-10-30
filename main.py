# main.py - Sistema de Asistencia (v1.0.1)
def registrar_asistencia(dni: str):
    dni_limpio = dni.strip()  # Fix: Limpieza de espacios en blanco
    if len(dni_limpio) >= 7 and dni_limpio.isdigit():
        print(f"[OK] Asistencia registrada exitosamente para DNI: {dni_limpio}")
        return True
    print("[ERROR] DNI invalido")
    return False

if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v1.0.1 ===")
    registrar_asistencia(" 40123456 ")