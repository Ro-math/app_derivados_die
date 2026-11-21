#!/usr/bin/env python3
"""
=============================================================================
LANZADOR UNIVERSAL DE LA APLICACIÓN DE DERIVADOS FX (WINDOWS Y MAC)
=============================================================================
Uso:
  Windows:
    run.bat web
    run.bat consola
    run.bat comand
    (o mediante: python run.py [web|consola|comand])

  Mac / Linux:
    ./run.sh web
    ./run.sh consola
    ./run.sh comand
    (o mediante: python3 run.py [web|consola|comand])

Este script:
1. Comprueba si el Python del sistema ya cuenta con las librerías necesarias.
2. Si no, crea un entorno virtual nativo para el sistema operativo
   (venv_win en Windows o venv en Mac) para evitar conflictos con OneDrive.
3. Instala automáticamente numpy, pandas y matplotlib solo la primera vez.
4. En las siguientes ejecuciones arranca directamente en menos de 1 segundo.
=============================================================================
"""

import os
import sys
import subprocess

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
REQ_FILE = os.path.join(BASE_DIR, "requirements.txt")
APP_SCRIPT = os.path.join(BASE_DIR, "app_derivados_fx.py")

# Separar el entorno de Windows del de Mac para evitar corrupción al sincronizar carpetas en OneDrive
if sys.platform == "win32":
    VENV_DIR = os.path.join(BASE_DIR, "venv_win")
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
else:
    VENV_DIR = os.path.join(BASE_DIR, "venv")
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")


def probar_librerias(py_exe):
    """Comprueba si el intérprete de python puede importar las librerías necesarias."""
    if not py_exe or not os.path.exists(py_exe):
        return False
    try:
        res = subprocess.run(
            [py_exe, "-c", "import numpy, pandas, matplotlib"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return res.returncode == 0
    except Exception:
        return False


def asegurar_entorno():
    """Garantiza la disponibilidad de un intérprete de Python con las librerías requeridas."""
    # 1. Si el Python global del usuario ya tiene las librerías, usarlo directamente
    if probar_librerias(sys.executable):
        return sys.executable

    # 2. Si el entorno virtual del sistema operativo ya existe y tiene las librerías, usarlo de inmediato
    if probar_librerias(VENV_PYTHON):
        return VENV_PYTHON

    # 3. Si no existe el ejecutable del entorno virtual, crearlo
    print("\n" + "="*62)
    os_name = "Windows" if sys.platform == "win32" else "macOS / Linux"
    print(f"  CONFIGURACIÓN INICIAL DEL ENTORNO ({os_name})")
    print("="*62)

    candidato_python = sys.executable

    if not os.path.exists(VENV_PYTHON):
        print(f"[1/2] Creando entorno virtual local '{os.path.basename(VENV_DIR)}'...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "venv", VENV_DIR],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if os.path.exists(VENV_PYTHON):
                candidato_python = VENV_PYTHON
        except Exception as e:
            print(f"[Aviso] No se pudo crear el entorno virtual aislado: {e}")
            print(f"Se intentará configurar directamente en el Python actual: {sys.executable}")
            candidato_python = sys.executable
    else:
        candidato_python = VENV_PYTHON

    # 4. Instalar las dependencias en el intérprete seleccionado
    print("[2/2] Instalando librerías científicas (numpy, pandas, matplotlib)...")
    print("      Por favor espera unos segundos mientras concluye la descarga...")

    instalado = False

    # Intento A: desde requirements.txt
    if os.path.exists(REQ_FILE):
        try:
            subprocess.check_call([candidato_python, "-m", "pip", "install", "-r", REQ_FILE])
            instalado = probar_librerias(candidato_python)
        except Exception:
            pass

    # Intento B: instalación directa de los paquetes básicos
    if not instalado:
        try:
            subprocess.check_call([candidato_python, "-m", "pip", "install", "numpy", "pandas", "matplotlib"])
            instalado = probar_librerias(candidato_python)
        except Exception as e:
            print(f"[Aviso] Error en pip al instalar paquetes: {e}")

    # Intento C: si falló en el entorno virtual, intentar en el python global del usuario
    if not instalado and candidato_python != sys.executable:
        try:
            print("[Reintento] Instalando en el Python de usuario...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "numpy", "pandas", "matplotlib"])
            if probar_librerias(sys.executable):
                candidato_python = sys.executable
                instalado = True
        except Exception:
            pass

    if instalado:
        print("[Listo] Librerías instaladas correctamente. Iniciando aplicación...\n")
    else:
        print("[Aviso] No se pudieron instalar librerías externas vía red.")
        print("        Se ejecutará el motor matemático integrado en Python nativo.\n")

    return candidato_python


def obtener_modo():
    """Detecta el sufijo pasado como argumento o solicita uno."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower().replace("-", "")
        if arg in ["web", "w"]:
            return "web"
        elif arg in ["consola", "console", "c", "interactivo"]:
            return "consola"
        elif arg in ["comand", "command", "cmd", "batch"]:
            return "comand"

    print("\n" + "="*60)
    print("  APLICACIÓN DE DERIVADOS FX Y GESTIÓN DE RIESGO (USD/MXN)")
    print("="*60)
    print("  Seleccione el modo de ejecución:")
    print("  [1] web     -> Interfaz visual en navegador (muestra la liga)")
    print("  [2] consola -> Cotizador interactivo en terminal")
    print("  [3] comand  -> Ejecución directa por comando con P&L y VaR")
    print("="*60)
    
    try:
        eleccion = input("Ingrese sufijo o número [web / consola / comand] (por defecto: web): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nOperación cancelada.")
        sys.exit(0)

    if eleccion in ["2", "consola", "c"]:
        return "consola"
    elif eleccion in ["3", "comand", "cmd"]:
        return "comand"
    return "web"


def main():
    modo = obtener_modo()
    python_exe = asegurar_entorno()

    if modo == "web":
        print("\n" + "="*62)
        print("  MODO WEB SELECCIONADO")
        print("  Iniciando servidor local y abriendo navegador...")
        print("  Si no abre automáticamente, ingresa a la siguiente liga:")
        print("  >>> http://localhost:8000 <<< (o 8001 si 8000 está ocupado)")
        print("  (Presiona Ctrl+C para detener el servidor)")
        print("="*62 + "\n")
        cmd = [python_exe, APP_SCRIPT, "web"]
    elif modo == "consola":
        cmd = [python_exe, APP_SCRIPT, "consola"]
    elif modo == "comand":
        cmd = [python_exe, APP_SCRIPT, "comand"] + sys.argv[2:]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nPrograma finalizado por el usuario.")


if __name__ == "__main__":
    main()
