# Gestor de Impresión y Escaneo

Aplicación de escritorio **100 % local** para administrar impresoras, imprimir, gestionar cola, escanear y crear PDF multipágina.

| Sistema   | Impresión / cola | Escaneo        |
|-----------|------------------|----------------|
| Windows   | win32print       | WIA (COM)      |
| Linux     | CUPS (`lp`, `lpstat`) | SANE (`scanimage`) |

- Python 3 + **CustomTkinter** (interfaz) + Tkinter embebido (tablas y vista previa)  
- Imágenes y PDF: **Pillow**  
- Windows: **pywin32** (solo en Windows, vía `requirements.txt`)  
- Empaquetado Windows: **PyInstaller**

Sin red, bases de datos ni servidores HTTP.

## Descarga rápida (sin clonar)

| Plataforma | Archivo |
|------------|---------|
| **Windows** | [`releases/GestorImpresionEscaneo.exe`](releases/GestorImpresionEscaneo.exe) (~20 MB) |
| **Linux** | [`releases/printer-app-linux.tar.gz`](releases/printer-app-linux.tar.gz) — descomprimir y ejecutar `install/linux/install.sh` |

En GitHub: pestaña **Code** → carpeta `releases/`, o **Download raw file** en cada enlace.

---

## Logo e icono

- `assets/logo.png` — logo en la barra superior de la app  
- `assets/icon.ico` — icono de ventana y del `.exe`  

Regenerar (opcional):

```bash
python scripts/generate_branding.py
```

---

## Windows — instalación

### Requisitos

- Windows 10 u 11  
- [Python 3.10+](https://www.python.org/downloads/) (marcar **Add python.exe to PATH**)  
- Drivers de impresora y escáner ya instalados en Windows  

### Opción A — desde código (desarrollo)

En **CMD** o **PowerShell**:

```cmd
cd C:\Users\TU_USUARIO\Documents\printer-app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts\generate_branding.py
python main.py
```

En **Git Bash** (activar venv con barras `/`):

```bash
cd ~/Documents/printer-app
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
python scripts/generate_branding.py
python main.py
```

### Opción B — ejecutable (.exe, sin Python en el PC destino)

En el PC donde desarrollas, con el venv activo:

```cmd
pip install pyinstaller
pyinstaller build.spec
```

Copia a cualquier PC Windows:

`dist\GestorImpresionEscaneo.exe`

No incluye drivers; el equipo debe tener impresora/escáner configurados en Windows.

### Acceso directo manual (Windows)

1. Clic derecho en el escritorio → **Nuevo** → **Acceso directo**  
2. Destino: `C:\...\printer-app\venv\Scripts\pythonw.exe C:\...\printer-app\main.py`  
   (o la ruta al `.exe` de `dist\`)  
3. **Cambiar icono** → elegir `assets\icon.ico`

---

## Linux — instalación

### Requisitos del sistema

- **CUPS** — `lp`, `lpstat`, `cancel`, `lpoptions`  
- **SANE** — `scanimage`  
- **Python 3** + **python3-tk** + **python3-venv**  

### Opción A — script (Debian / Ubuntu)

```bash
cd ~/Documents/printer-app
chmod +x install/linux/install.sh install/linux/run.sh
./install/linux/install.sh
./install/linux/run.sh
```

El script instala paquetes del sistema, crea `venv`, instala pip deps y un acceso directo en el menú de aplicaciones.

### Opción B — manual (cualquier distro con apt/dnf/pacman equivalente)

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install python3 python3-venv python3-tk sane-utils cups cups-client

cd ~/Documents/printer-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/generate_branding.py
python main.py
```

### Permisos escáner (SANE)

```bash
sudo usermod -aG scanner "$USER"
# Cerrar sesión y volver a entrar
scanimage -L
```

### Acceso directo

Tras `install.sh`: `~/.local/share/applications/printer-scanner-manager.desktop`  

Lanzador manual: `install/linux/run.sh`

---

## Pruebas sin interfaz

```bash
python scripts/enumerate_printers.py
python scripts/enumerate_scanners.py
```

---

## Escaneo — flujo en la app

1. Escanear → **vista previa con scroll** (no guarda en disco)  
2. Revisar imagen completa (rueda del ratón / barras)  
3. **Guardar documento…** cuando esté conforme  
4. Varias páginas: **Agregar al documento** → guardar como PDF  

---

## Configuración

Archivo `config.json` en la raíz del proyecto (pestaña **Configuración**).

Logs: `logs/app.log`

---

## Solución de problemas

### Windows — no hay escáneres WIA

- Compruebe *Impresoras y escáneres* en Configuración de Windows.  
- Cierre otras apps que usen el escáner.  
- `python scripts/enumerate_scanners.py`

### Linux — no hay escáneres

- `scanimage -L` en terminal.  
- Instale el backend SANE del fabricante (`sane-airscan`, `hplip`, etc.).  
- Grupo `scanner` y permisos udev.

### Linux — impresión

- `lpstat -p -d`  
- Cola: `lpstat -o NombreImpresora`

---

## Estructura

```
app/
  backends/     # Windows vs Linux
  ui.py
  platform.py
  theming.py
install/linux/  # instalador y .desktop
main.py
```
