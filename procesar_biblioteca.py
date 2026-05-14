import pymupdf4llm
import sqlite3
import os
import re
from pathlib import Path

CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
TAMANO_MAX_PARRAFO = 10000
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

def limpiar_markdown_y_duplicados(texto, titulo_libro=""):
    """Elimina símbolos Markdown y títulos duplicados."""
    if not texto:
        return ""
    # Eliminar cabeceras Markdown (líneas que empiezan con #)
    texto = re.sub(r'(?m)^#+\s*', '', texto)
    # Eliminar énfasis _texto_ o *texto*
    texto = re.sub(r'[_\*]([^_\*]+)[_\*]', r'\1', texto)
    # Eliminar negritas dobles
    texto = re.sub(r'\*\*([^\*]+)\*\*', r'\1', texto)
    # Eliminar líneas que sean exactamente el título (para evitar duplicados)
    if titulo_libro:
        patron_titulo = re.compile(r'^\s*' + re.escape(titulo_libro) + r'\s*$', re.MULTILINE | re.IGNORECASE)
        texto = patron_titulo.sub('', texto, count=1)
    return texto.strip()

def extraer_texto_layout(ruta_pdf):
    try:
        md = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
        return md
    except Exception as e:
        log(f"Error layout: {e}")
        return None

def dividir_parrafos(texto):
    """Divide por doble salto de línea y asigna números."""
    bloques = texto.split('\n\n')
    parrafos = []
    contador = 1
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        # Extraer número si existe al inicio
        match = re.match(r'^\s*(\d+)(?:\.|\)|\s)+', bloque)
        if match:
            num = int(match.group(1))
            contenido = re.sub(r'^\s*\d+(?:\.|\)|\s)+', '', bloque).strip()
        else:
            num = contador
            contenido = bloque
            contador += 1
        if len(contenido) > TAMANO_MAX_PARRAFO:
            contenido = contenido[:TAMANO_MAX_PARRAFO]
        parrafos.append((num, contenido))
    return parrafos

def extraer_titulo(texto_md, nombre_archivo, codigo):
    """Extrae el título real: primera línea no vacía después de limpiar símbolos."""
    texto_limpio = limpiar_markdown_y_duplicados(texto_md)
    lineas = texto_limpio.split('\n')
    for linea in lineas:
        linea = linea.strip()
        if linea and len(linea) < 100 and not re.search(r'SPN\d{2}-\d{4}', linea):
            if not re.search(r'(copyright|derechos|reservados|www)', linea, re.IGNORECASE):
                return linea.upper()
    # fallback
    titulo = re.sub(r'^' + re.escape(codigo) + r'\s*', '', nombre_archivo)
    titulo = titulo.replace('_', ' ').replace('VGR', '').strip().upper()
    return titulo

def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    nombre_archivo = Path(ruta_pdf).stem
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else nombre_archivo.split()[0]

    md_text = extraer_texto_layout(ruta_pdf)
    if not md_text:
        return 0

    titulo_raw = extraer_titulo(md_text, nombre_archivo, codigo)
    texto_limpio = limpiar_markdown_y_duplicados(md_text, titulo_raw)
    titulo_final = extraer_titulo(texto_limpio, nombre_archivo, codigo)
    titulo_formateado = f"{codigo} {titulo_final}"

    parrafos = dividir_parrafos(texto_limpio)

    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_formateado, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()

    total = 0
    for num_par, cont in parrafos:
        cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                    (libro_id, num_par, cont))
        total += 1
        if total % 100 == 0:
            conn.commit()
    conn.commit()
    log(f"  -> {total} párrafos")
    return total

# ========== BASE DE DATOS Y MAIN ==========
def inicializar_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS libros")
    cur.execute("DROP TABLE IF EXISTS parrafos")
    cur.execute("DROP TABLE IF EXISTS parrafos_fts")
    cur.execute("""
        CREATE TABLE libros (
            id INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            codigo TEXT NOT NULL,
            fecha TEXT NOT NULL DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE parrafos (
            id INTEGER PRIMARY KEY,
            libro_id INTEGER NOT NULL,
            numero_parrafo INTEGER NOT NULL,
            contenido TEXT NOT NULL,
            FOREIGN KEY(libro_id) REFERENCES libros(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE VIRTUAL TABLE parrafos_fts USING fts5(
            contenido,
            content=parrafos,
            content_rowid=id,
            tokenize='unicode61'
        )
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS parrafos_ai AFTER INSERT ON parrafos BEGIN
            INSERT INTO parrafos_fts(rowid, contenido) VALUES (new.id, new.contenido);
        END
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS parrafos_ad AFTER DELETE ON parrafos BEGIN
            INSERT INTO parrafos_fts(parrafos_fts, rowid, contenido) VALUES('delete', old.id, old.contenido);
        END
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS parrafos_au AFTER UPDATE ON parrafos BEGIN
            INSERT INTO parrafos_fts(parrafos_fts, rowid, contenido) VALUES('delete', old.id, old.contenido);
            INSERT INTO parrafos_fts(rowid, contenido) VALUES (new.id, new.contenido);
        END
    """)
    conn.commit()
    return conn

def procesar():
    conn = inicializar_db()
    archivos = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith('.pdf')]
    if not archivos:
        log("No hay PDFs")
        conn.close()
        return
    total_gral = 0
    for arch in archivos:
        ruta = os.path.join(CARPETA_PDFS, arch)
        try:
            total_gral += procesar_pdf(conn, ruta)
        except Exception as e:
            log(f"Error en {arch}: {e}")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    log(f"Total párrafos: {total_gral}")

if __name__ == "__main__":
    procesar()