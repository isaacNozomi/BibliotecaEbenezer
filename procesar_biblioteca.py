import pymupdf4llm
import sqlite3
import os
import re
from pathlib import Path

CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

# ------------------------------------------------------------
# LIMPIEZA Y CLASIFICACIÓN
# ------------------------------------------------------------
def es_linea_basura(linea):
    """Detecta líneas que deben eliminarse por completo."""
    l = linea.strip()
    if not l:
        return True
    # Números de página solos
    if re.match(r'^\d+$', l):
        return True
    patrones_basura = [
        r'^===== Page \d+ =====$', r'^LA PALABRA HABLADA$', r'^SPANISH$',
        r'©20\d{2} VGR', r'GRABACIONES "LA VOZ DE DIOS"', r'P\.O\. BOX \d+',
        r'www\.branham\.org', r'Todos los derechos reservados',
        r'Nota Sobre Los Derechos de Autor', r'Voice of God Recordings',
        r'^Este Mensaje por el Hermano', r'^SPN\d{2}-\d{4}\s+\w+',
        r'^\d+\s+LA\s+PALABRA\s+HABLADA',
    ]
    for pat in patrones_basura:
        if re.search(pat, l, re.IGNORECASE):
            return True
    return False

def limpiar_markdown(md_texto, titulo_principal=""):
    """
    Elimina líneas basura, símbolos markdown molestos,
    y evita duplicar el título principal.
    """
    lineas = md_texto.split('\n')
    lineas_limpias = []
    for linea in lineas:
        if es_linea_basura(linea):
            continue
        # Eliminar cabeceras markdown (#, ##, etc.)
        linea = re.sub(r'^#{1,6}\s*', '', linea)
        # Eliminar énfasis _texto_ y *texto* (pero conservar el texto interno)
        linea = re.sub(r'[*_]([^*_]+)[*_]', r'\1', linea)
        # Eliminar negritas dobles
        linea = re.sub(r'\*\*([^*]+)\*\*', r'\1', linea)
        # Si la línea es exactamente el título principal (evitar duplicado)
        if titulo_principal and linea.strip().lower() == titulo_principal.lower():
            continue
        if linea.strip():
            lineas_limpias.append(linea)
    return '\n'.join(lineas_limpias)

def extraer_titulo_y_codigo(ruta_pdf, nombre_archivo):
    """
    Devuelve (codigo, titulo_principal) donde titulo_principal es el título real en español.
    """
    # Primero extraemos el markdown para buscar el título
    md = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
    if not md:
        # Fallback: usar nombre de archivo
        nombre = Path(nombre_archivo).stem
        codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre)
        codigo = codigo_match.group(1) if codigo_match else "SPN00-0000"
        titulo = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre).replace('_', ' ').strip().upper()
        return codigo, titulo

    # Buscar código en el markdown o en el nombre
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', md)
    if not codigo_match:
        codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else "SPN00-0000"

    # Buscar título real: primera línea no vacía, no basura, en mayúsculas, longitud razonable
    titulo = None
    for linea in md.split('\n'):
        l = linea.strip()
        if len(l) > 10 and len(l) < 150 and l.isupper():
            # evitar falsos positivos
            if not re.search(r'PALABRA|HABLADA|DERECHOS|COPYRIGHT|SPN\d{2}-\d{4}', l, re.IGNORECASE):
                titulo = l
                break
    if not titulo:
        # fallback: usar nombre de archivo
        titulo = Path(nombre_archivo).stem
        titulo = re.sub(r'^SPN\d{2}-\d{4}\s*', '', titulo).replace('_', ' ').strip().upper()
    return codigo, titulo

def clasificar_bloque(bloque, titulo_principal=""):
    """
    Analiza un bloque (párrafo) y devuelve (numero, contenido_limpio, tipo)
    tipo: 0 normal, 1 título interno, 2 cita bíblica
    """
    lineas = bloque.split('\n')
    if not lineas:
        return 0, "", 0

    primera = lineas[0].strip()
    # Detectar cita bíblica: la primera línea empieza con '>' (markdown blockquote)
    if primera.startswith('>'):
        tipo = 2
        # Quitar todos los '>' del bloque
        contenido = re.sub(r'^>\s*', '', bloque, flags=re.MULTILINE)
    else:
        # Detectar título interno: primera línea corta, mayúsculas, sin números
        if (len(primera) < 80 and primera.isupper() and not re.search(r'\d', primera) and
            not re.search(r'copyright|derechos', primera, re.IGNORECASE)):
            tipo = 1
            contenido = bloque
        else:
            tipo = 0
            contenido = bloque

    # Extraer número de párrafo si está al inicio
    contenido = contenido.strip()
    num = 0
    match = re.match(r'^(\d+)(?:\.|\s+|\))', contenido)
    if match:
        num = int(match.group(1))
        contenido = re.sub(r'^\d+(?:\.|\s+|\))', '', contenido).strip()

    # Limpiar símbolos markdown residuales (sin dañar [] ni ...)
    contenido = re.sub(r'[*_]([^*_]+)[*_]', r'\1', contenido)
    contenido = re.sub(r'\*\*([^*]+)\*\*', r'\1', contenido)
    contenido = re.sub(r'#{1,6}\s*', '', contenido)

    return num, contenido, tipo

def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    nombre_archivo = Path(ruta_pdf).name

    # 1. Extraer código y título real
    codigo, titulo_principal = extraer_titulo_y_codigo(ruta_pdf, nombre_archivo)
    titulo_completo = f"{codigo} {titulo_principal}"
    log(f"  Título extraído: {titulo_completo}")

    # 2. Obtener markdown con layout
    md_raw = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
    if not md_raw:
        log(f"  Error: no se pudo extraer texto")
        return 0

    # 3. Limpiar markdown (eliminar basura y título duplicado)
    md_limpio = limpiar_markdown(md_raw, titulo_principal)

    # 4. Dividir en bloques (párrafos) por doble salto de línea
    bloques = md_limpio.split('\n\n')
    bloques = [b.strip() for b in bloques if b.strip()]

    # 5. Insertar libro en BD (título completo)
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_completo, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()

    # 6. Procesar cada bloque y guardar
    total = 0
    contador_correlativo = 1
    for bloque in bloques:
        num_original, contenido, tipo = clasificar_bloque(bloque, titulo_principal)
        if not contenido:
            continue
        # Si no tenía número, asignamos correlativo
        if num_original == 0:
            num_original = contador_correlativo
            contador_correlativo += 1
        else:
            contador_correlativo = max(contador_correlativo, num_original + 1)

        cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido, tipo) VALUES (?, ?, ?, ?)",
                    (libro_id, num_original, contenido, tipo))
        total += 1
        if total % 100 == 0:
            conn.commit()
    conn.commit()
    log(f"  -> {total} párrafos guardados.")
    return total

# ------------------------------------------------------------
# BASE DE DATOS (con columna tipo)
# ------------------------------------------------------------
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
            tipo INTEGER DEFAULT 0,
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

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def procesar():
    conn = inicializar_db()
    archivos = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith('.pdf')]
    if not archivos:
        log(f"No se encontraron PDFs en '{CARPETA_PDFS}'")
        conn.close()
        return
    total_general = 0
    for archivo in archivos:
        ruta = os.path.join(CARPETA_PDFS, archivo)
        try:
            total_general += procesar_pdf(conn, ruta)
        except Exception as e:
            log(f"Error con {archivo}: {e}")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    log(f"✅ Procesamiento completado. Total párrafos: {total_general}")
    print("Base de datos generada exitosamente.")

if __name__ == "__main__":
    procesar()