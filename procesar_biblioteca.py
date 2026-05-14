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
# LIMPIEZA DE BASURA
# ------------------------------------------------------------
def es_linea_basura(linea, titulo_principal=""):
    """Detecta líneas que deben eliminarse por completo."""
    l = linea.strip()
    if not l:
        return True
    
    # Números de página solos
    if re.match(r'^\d+$', l):
        return True
    
    # Patrones fijos de basura
    patrones_basura = [
        r'^===== Page \d+ =====$',
        r'^LA\s+PALABRA\s+HABLADA$',
        r'^\d+\s+LA\s+PALABRA\s+HABLADA',
        r'^SPANISH$',
        r'©20\d{2}\s+VGR',
        r'GRABACIONES\s+["\']?LA VOZ DE DIOS["\']?',
        r'P\.O\.\s+BOX\s+\d+',
        r'www\.branham\.org',
        r'Todos\s+los\s+derechos\s+reservados',
        r'Nota\s+Sobre\s+Los\s+Derechos\s+de\s+Autor',
        r'Voice\s+of\s+God\s+Recordings',
        r'Este\s+Mensaje\s+por\s+el\s+Hermano',
        r'^SPN\d{2}-\d{4}\s*$',
        r'Código:\s*SPN\d{2}-\d{4}',
        r'^VGR$',
        r'^\d+\s*$',
    ]
    for pat in patrones_basura:
        if re.search(pat, l, re.IGNORECASE):
            return True
    
    # Eliminar líneas que sean exactamente el título principal (pie de página)
    if titulo_principal:
        # Comparación exacta ignorando mayúsculas/minúsculas y espacios
        l_sin_espacios = re.sub(r'\s+', ' ', l).strip().lower()
        titulo_limpio = re.sub(r'\s+', ' ', titulo_principal).strip().lower()
        if l_sin_espacios == titulo_limpio:
            return True
        # También si la línea contiene el título rodeado de espacios
        if titulo_limpio in l_sin_espacios and len(l_sin_espacios) < len(titulo_limpio) + 10:
            return True
    
    return False

def limpiar_markdown(md_texto, titulo_principal=""):
    """Elimina basura y símbolos markdown sobrantes."""
    lineas = md_texto.split('\n')
    lineas_limpias = []
    
    for linea in lineas:
        if es_linea_basura(linea, titulo_principal):
            continue
        
        # Eliminar cabeceras markdown (#, ##, etc.)
        linea = re.sub(r'^#{1,6}\s*', '', linea)
        # Eliminar énfasis _texto_ y *texto*
        linea = re.sub(r'[*_]([^*_]+)[*_]', r'\1', linea)
        # Eliminar negritas dobles
        linea = re.sub(r'\*\*([^*]+)\*\*', r'\1', linea)
        # Eliminar ` (backticks)
        linea = re.sub(r'`([^`]+)`', r'\1', linea)
        
        if linea.strip():
            lineas_limpias.append(linea)
    
    return '\n'.join(lineas_limpias)

# ------------------------------------------------------------
# EXTRACCIÓN DE TÍTULO Y CÓDIGO
# ------------------------------------------------------------
def extraer_titulo_y_codigo(ruta_pdf, nombre_archivo):
    """Devuelve (codigo, titulo_completo_formateado, titulo_simple)"""
    md = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
    if not md:
        # Fallback
        nombre = Path(nombre_archivo).stem
        codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre)
        codigo = codigo_match.group(1) if codigo_match else "SPN00-0000"
        titulo_simple = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre).replace('_', ' ').strip().upper()
        titulo_simple = re.sub(r'\s+VGR\s*$', '', titulo_simple).strip()
        titulo_completo = f"{codigo} {titulo_simple}"
        return codigo, titulo_completo, titulo_simple
    
    # Extraer código
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', md)
    if not codigo_match:
        codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else "SPN00-0000"
    
    # Buscar título real
    titulo_simple = None
    for linea in md.split('\n'):
        l = linea.strip()
        # Limpiar markdown
        l_limpio = re.sub(r'^#{1,6}\s*', '', l)
        l_limpio = re.sub(r'[*_`]', '', l_limpio)
        if len(l_limpio) > 10 and len(l_limpio) < 150 and l_limpio.isupper():
            if not re.search(r'PALABRA|HABLADA|DERECHOS|COPYRIGHT|SPN\d{2}-\d{4}', l_limpio, re.IGNORECASE):
                titulo_simple = l_limpio
                break
    
    if not titulo_simple:
        # Usar nombre de archivo
        titulo_simple = Path(nombre_archivo).stem
        titulo_simple = re.sub(r'^SPN\d{2}-\d{4}\s*', '', titulo_simple)
        titulo_simple = titulo_simple.replace('_', ' ').replace('VGR', '').strip().upper()
    
    # Limpiar título simple de residuos
    titulo_simple = re.sub(r'[#*_`]', '', titulo_simple)
    titulo_simple = re.sub(r'\s+', ' ', titulo_simple).strip()
    titulo_completo = f"{codigo} {titulo_simple}"
    
    return codigo, titulo_completo, titulo_simple

# ------------------------------------------------------------
# CLASIFICACIÓN DE PÁRRAFOS
# ------------------------------------------------------------
def clasificar_bloque(bloque, titulo_simple=""):
    """Devuelve (numero_parrafo, contenido_limpio, tipo)"""
    if not bloque.strip():
        return 0, "", 0
    
    lineas = bloque.split('\n')
    primera = lineas[0].strip()
    
    # Detectar cita bíblica (empieza con >)
    if primera.startswith('>'):
        tipo = 2
        contenido = re.sub(r'^>\s*', '', bloque, flags=re.MULTILINE)
    else:
        # Detectar título interno
        es_titulo_interno = (
            len(primera) < 80 and
            primera.isupper() and
            not re.search(r'\d{4,}', primera) and
            not re.search(r'COPYRIGHT|DERECHOS|RESERVADOS|SPN|PALABRA|HABLADA', primera, re.IGNORECASE) and
            titulo_simple and
            primera.lower() != titulo_simple.lower()
        )
        tipo = 1 if es_titulo_interno else 0
        contenido = bloque
    
    contenido = contenido.strip()
    
    # Extraer número de párrafo
    num = 0
    match = re.match(r'^(\d+)(?:\.|\s+|\))', contenido)
    if match:
        num = int(match.group(1))
        contenido = re.sub(r'^\d+(?:\.|\s+|\))', '', contenido).strip()
    
    # Limpiar residuos markdown
    contenido = re.sub(r'[*_`]', '', contenido)
    contenido = re.sub(r'\*\*([^*]+)\*\*', r'\1', contenido)
    contenido = re.sub(r'#{1,6}\s*', '', contenido)
    contenido = re.sub(r'\s+', ' ', contenido)
    
    return num, contenido, tipo

# ------------------------------------------------------------
# PROCESAR UN PDF
# ------------------------------------------------------------
def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    nombre_archivo = Path(ruta_pdf).name
    
    # 1. Extraer código, título completo y título simple
    codigo, titulo_completo, titulo_simple = extraer_titulo_y_codigo(ruta_pdf, nombre_archivo)
    log(f"  Título extraído: {titulo_completo}")
    
    # 2. Obtener markdown con layout
    md_raw = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
    if not md_raw:
        log(f"  Error: no se pudo extraer texto")
        return 0
    
    # 3. Limpiar markdown (eliminar basura y títulos duplicados)
    md_limpio = limpiar_markdown(md_raw, titulo_simple)
    
    # 4. Dividir en párrafos por doble salto de línea
    bloques = md_limpio.split('\n\n')
    bloques = [b.strip() for b in bloques if b.strip()]
    
    # 5. Insertar libro en BD
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_completo, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()
    
    # 6. Procesar cada bloque
    total = 0
    contador_correlativo = 1
    
    for bloque in bloques:
        num_original, contenido, tipo = clasificar_bloque(bloque, titulo_simple)
        if not contenido:
            continue
        
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
# BASE DE DATOS
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