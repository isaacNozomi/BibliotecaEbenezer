import pymupdf4llm
import sqlite3
import os
import re
from pathlib import Path

# Configuración de rutas
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"

def log(msg):
    print(f"[INFO] {msg}")

def extraer_texto_estructurado(ruta_pdf):
    try:
        # Convertimos a Markdown para preservar la estructura de citas (>) y negritas
        return pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False)
    except Exception as e:
        log(f"Error extrayendo {ruta_pdf}: {e}")
        return None

def limpiar_y_clasificar(texto_raw):
    lineas = texto_raw.split('\n')
    parrafos_procesados = []
    
    bloque_actual = ""
    tipo_actual = 0 # 0: Normal, 1: Titulo, 2: Cita Bíblica

    # Palabras clave para eliminar (basura del PDF)
    blacklist = ["LA PALABRA HABLADA", "BRANHAM", "P.O. BOX", "RESERVADOS", "![](image"]

    for linea in lineas:
        l = linea.strip()
        
        # 1. Filtros de limpieza
        if not l or any(x in l.upper() for x in blacklist) or re.match(r'^\d+$', l):
            if bloque_actual:
                parrafos_procesados.append((bloque_actual.strip(), tipo_actual))
                bloque_actual = ""
                tipo_actual = 0
            continue

        # 2. Identificación de Títulos (Mayúsculas cortas)
        if l.isupper() and len(l) < 100:
            tipo_actual = 1
        
        # 3. Identificación de Citas Bíblicas (Indentadas o con formato Markdown)
        elif l.startswith(">") or linea.startswith("    "):
            tipo_actual = 2
            l = l.replace(">", "").strip()

        # Limpieza de símbolos Markdown residuales
        l = re.sub(r'[*_#]', '', l)
        bloque_actual += l + " "

    if bloque_actual:
        parrafos_procesados.append((bloque_actual.strip(), tipo_actual))
    
    return parrafos_procesados

def extraer_metadata(texto_raw):
    # Extraer código YY-MMDD
    codigo_match = re.search(r'(\d{2}-\d{4})', texto_raw)
    codigo = codigo_match.group(1) if codigo_match else "00-0000"
    
    # Extraer título (primera línea larga en mayúsculas)
    lineas = [l.strip() for l in texto_raw.split('\n') if len(l.strip()) > 10]
    titulo = "TITULO DESCONOCIDO"
    for l in lineas:
        if l.isupper() and "PALABRA" not in l:
            titulo = l
            break
            
    return f"SPN{codigo} {titulo}", codigo

def inicializar_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS libros;
        DROP TABLE IF EXISTS parrafos;
        CREATE TABLE libros (id INTEGER PRIMARY KEY, titulo TEXT, codigo TEXT, fecha TEXT);
        CREATE TABLE parrafos (
            id INTEGER PRIMARY KEY, 
            libro_id INTEGER, 
            numero_parrafo INTEGER, 
            contenido TEXT, 
            tipo INTEGER, 
            FOREIGN KEY(libro_id) REFERENCES libros(id)
        );
    """)
    return conn

def procesar():
    if not os.path.exists(CARPETA_PDFS):
        os.makedirs(CARPETA_PDFS)
        log(f"Crea la carpeta '{CARPETA_PDFS}' y mete tus PDFs ahí.")
        return

    conn = inicializar_db()
    archivos = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith('.pdf')]
    
    for archivo in archivos:
        ruta = os.path.join(CARPETA_PDFS, archivo)
        texto_raw = extraer_texto_estructurado(ruta)
        if not texto_raw: continue
        
        titulo_menu, codigo = extraer_metadata(texto_raw)
        
        cur = conn.cursor()
        cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)", (titulo_menu, codigo, "2025"))
        libro_id = cur.lastrowid
        
        bloques = limpiar_y_clasificar(texto_raw)
        
        for i, (cont, tipo) in enumerate(bloques):
            cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido, tipo) VALUES (?,?,?,?)",
                        (libro_id, i+1, cont, tipo))
        
        log(f"Procesado con éxito: {titulo_menu}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    procesar()