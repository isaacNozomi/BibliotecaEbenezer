import pymupdf4llm
import sqlite3
import os
import re
from pathlib import Path

# ================= CONFIGURACIÓN =================
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

# ================= LIMPIEZA DE BASURA =================
def es_linea_basura(linea):
    """Detecta líneas que deben eliminarse por completo (números de página, encabezados, copyright, etc.)"""
    l = linea.strip()
    if not l:
        return True
    # Números de página solos
    if re.match(r'^\d+$', l):
        return True
    # Patrones fijos de basura
    basura = [
        r'^===== Page \d+ =====$', r'^LA PALABRA HABLADA$', r'^SPANISH$',
        r'©20\d{2} VGR', r'GRABACIONES "LA VOZ DE DIOS"', r'P\.O\. BOX \d+',
        r'www\.branham\.org', r'Todos los derechos reservados',
        r'Nota Sobre Los Derechos de Autor', r'Voice of God Recordings',
        r'^Este Mensaje por el Hermano', r'^SPN\d{2}-\d{4} \w+',
        r'^EL CAMINO DE DIOS',  # para no confundir con título principal (lo tratamos aparte)
    ]
    for patron in basura:
        if re.search(patron, l, re.IGNORECASE):
            return True
    return False

def limpiar_markdown(texto_md):
    """
    Elimina líneas basura, símbolos markdown sobrantes y normaliza.
    Conserva las citas (líneas que empiezan con '>') y los números de párrafo.
    """
    lineas = texto_md.split('\n')
    lineas_limpias = []
    for linea in lineas:
        if es_linea_basura(linea):
            continue
        # Eliminar símbolos markdown que no queremos (#, *, _, etc.) pero respetando '>' y números
        # No eliminar números de párrafo al inicio de línea (ej "2 ")
        # Pero sí eliminar '#' de encabezados (ya los capturamos como título aparte)
        if linea.startswith('#'):
            linea = re.sub(r'^#+\s*', '', linea)
        # Eliminar énfasis markdown pero conservar el texto interno
        linea = re.sub(r'[*_]([^*_]+)[*_]', r'\1', linea)
        # Quitar espacios múltiples
        linea = re.sub(r'[ \t]+', ' ', linea)
        lineas_limpias.append(linea)
    return '\n'.join(lineas_limpias)

def extraer_titulo_y_codigo_desde_pdf(ruta_pdf, nombre_archivo):
    """
    Extrae el título real y el código del libro.
    Prioridad: 
      1. Buscar en el texto del PDF una línea que parezca título (mayúsculas, longitud media)
      2. Si no, usar el nombre del archivo (sin extensión) y limpiarlo.
    El código (SPNxx-xxxx) lo extrae del nombre del archivo o del interior.
    """
    doc = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
    if not doc:
        # Fallback: solo con nombre de archivo
        nombre = Path(nombre_archivo).stem
        match = re.search(r'(SPN\d{2}-\d{4})', nombre)
        codigo = match.group(1) if match else "SPN00-0000"
        titulo = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre).replace('_', ' ').strip().upper()
        return codigo, titulo

    # Buscar título: primera línea no vacía, en mayúsculas, con longitud entre 10 y 100, que no sea basura
    lineas = doc.split('\n')
    titulo_candidato = None
    for linea in lineas:
        l = linea.strip()
        if len(l) > 10 and len(l) < 100 and l.isupper() and not es_linea_basura(l):
            # Evitar falsos como "LA PALABRA HABLADA"
            if not re.search(r'PALABRA|HABLADA|DERECHOS|COPYRIGHT', l, re.IGNORECASE):
                titulo_candidato = l
                break
    # Si no se encuentra, usar nombre de archivo limpio
    if not titulo_candidato:
        nombre = Path(nombre_archivo).stem
        titulo_candidato = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre).replace('_', ' ').strip().upper()
    # Extraer código
    match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = match.group(1) if match else "SPN00-0000"
    return codigo, titulo_candidato

def clasificar_bloque(bloque):
    """
    Dado un bloque de texto (puede ser varias líneas), determina su tipo:
    0 = normal
    1 = título interno (línea corta en mayúsculas)
    2 = cita bíblica (comienza con '>' o está indentada)
    También extrae el número de párrafo si lo tiene al inicio.
    Devuelve (numero_parrafo, contenido_limpio, tipo)
    """
    linea_inicial = bloque.split('\n')[0].strip()
    # Detectar cita: línea que empieza con '>' (markdown de blockquote) o que tiene indentación
    if linea_inicial.startswith('>'):
        tipo = 2
        # Quitar el '>' y espacios
        contenido = re.sub(r'^>\s*', '', bloque, flags=re.MULTILINE)
    elif linea_inicial.isupper() and len(linea_inicial) < 80 and not re.search(r'\d', linea_inicial):
        # Posible título interno
        tipo = 1
        contenido = bloque
    else:
        tipo = 0
        contenido = bloque

    # Extraer número de párrafo (si existe al inicio del contenido)
    match = re.match(r'^\s*(\d+)(?:\.|\s)', contenido)
    if match:
        num = int(match.group(1))
        # Eliminar el número del contenido
        contenido = re.sub(r'^\s*\d+(?:\.|\s)', '', contenido).strip()
    else:
        num = 0  # luego se asignará correlativo si es necesario

    # Limpiar residuos de markdown dentro del contenido
    contenido = re.sub(r'[*_]([^*_]+)[*_]', r'\1', contenido)
    # Eliminar múltiples espacios
    contenido = re.sub(r'[ \t]+', ' ', contenido)
    return num, contenido.strip(), tipo

def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    nombre_archivo = Path(ruta_pdf).name

    # 1. Extraer código y título principal
    codigo, titulo_principal = extraer_titulo_y_codigo_desde_pdf(ruta_pdf, nombre_archivo)
    titulo_libro = f"{codigo} {titulo_principal}"
    log(f"  Título extraído: {titulo_libro}")

    # 2. Extraer todo el texto con layout mode (markdown)
    md_raw = pymupdf4llm.to_markdown(ruta_pdf, page_chunks=False, write_images=False, use_llm=False)
    if not md_raw:
        log(f"  Error: no se pudo extraer texto de {ruta_pdf}")
        return 0

    # 3. Limpiar markdown de basura
    texto_limpio = limpiar_markdown(md_raw)

    # 4. Dividir en bloques (párrafos) por doble salto de línea
    bloques = texto_limpio.split('\n\n')
    bloques_filtrados = []
    for b in bloques:
        if b.strip():
            bloques_filtrados.append(b)

    # 5. Insertar libro en BD
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_libro, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()

    # 6. Procesar cada bloque y guardar párrafos
    num_parrafo_correlativo = 1
    total = 0
    for bloque in bloques_filtrados:
        # Clasificar y extraer número y tipo
        num_original, contenido, tipo = clasificar_bloque(bloque)
        if not contenido:
            continue
        # Si el bloque no tenía número, asignamos correlativo
        if num_original == 0:
            num_original = num_parrafo_correlativo
            num_parrafo_correlativo += 1
        else:
            # Si tenía número, actualizamos el correlativo para que no haya conflicto
            num_parrafo_correlativo = max(num_parrafo_correlativo, num_original + 1)

        # Guardar
        cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido, tipo) VALUES (?, ?, ?, ?)",
                    (libro_id, num_original, contenido, tipo))
        total += 1
        if total % 100 == 0:
            conn.commit()
    conn.commit()
    log(f"  -> {total} párrafos guardados.")
    return total

# ================= BASE DE DATOS (con columna tipo) =================
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

# ================= PROGRAMA PRINCIPAL =================
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