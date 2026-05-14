import fitz
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

def extraer_texto_estructurado(ruta_pdf):
    log("  -> Extrayendo con layout mode...")
    try:
        md_text = pymupdf4llm.to_markdown(
            ruta_pdf,
            page_chunks=False,
            write_images=False,
            use_llm=False
        )
        return md_text
    except Exception as e:
        log(f"  Error: {e}")
        return None

def limpieza_profunda(texto, titulo_libro=""):
    """
    Limpieza extrema pero respetando corchetes, puntos suspensivos, etc.
    Elimina: símbolos Markdown, números de página sueltos, líneas de código, títulos duplicados.
    """
    if not texto:
        return ""
    
    lineas = texto.split('\n')
    lineas_limpias = []
    
    for linea in lineas:
        linea_original = linea
        linea = linea.strip()
        
        # === ELIMINAR LÍNEAS BASURA COMPLETAS ===
        # Números de página solos
        if re.match(r'^\d+$', linea):
            continue
        # Líneas con "Código: SPN..." o "SPN..." solos
        if re.search(r'Código:\s*SPN\d{2}-\d{4}', linea, re.IGNORECASE):
            continue
        if re.match(r'^SPN\d{2}-\d{4}\s*$', linea, re.IGNORECASE):
            continue
        # Encabezados repetitivos
        if re.search(r'^LA\s+PALABRA\s+HABLADA', linea, re.IGNORECASE):
            continue
        if re.search(r'(todos los derechos reservados|copyright|©|www\.branham|P\.O\. Box)', linea, re.IGNORECASE):
            continue
        # Líneas que son exactamente el título (evitar duplicado)
        if titulo_libro and linea.lower() == titulo_libro.lower():
            continue
        # Líneas que contienen el título con símbolos Markdown alrededor (## _Título_)
        if titulo_libro and re.search(r'#{1,6}\s*[_\*]*' + re.escape(titulo_libro) + r'[_\*]*', linea, re.IGNORECASE):
            continue
        
        # === LIMPIAR SÍMBOLOS MARKDOWN DENTRO DE LA LÍNEA (sin dañar corchetes) ===
        # Eliminar cabeceras Markdown (#, ##, ###)
        linea = re.sub(r'^#{1,6}\s*', '', linea)
        # Eliminar énfasis _texto_ y *texto*
        linea = re.sub(r'[_\*]([^_\*]+)[_\*]', r'\1', linea)
        # Eliminar negritas dobles
        linea = re.sub(r'\*\*([^\*]+)\*\*', r'\1', linea)
        # Eliminar el símbolo > al inicio de línea (citas)
        linea = re.sub(r'^>\s*', '', linea)
        
        # No eliminar corchetes [] ni puntos suspensivos ...
        # Solo si la línea no quedó vacía, la agregamos
        if linea.strip():
            lineas_limpias.append(linea)
    
    # Unir de nuevo
    texto_limpio = '\n'.join(lineas_limpias)
    
    # Eliminar dobles saltos de línea excesivos
    texto_limpio = re.sub(r'\n\s*\n', '\n\n', texto_limpio)
    return texto_limpio.strip()

def dividir_en_parrafos(texto):
    """Divide por doble salto de línea. Asigna números correlativos, sin símbolos extra."""
    bloques = texto.split('\n\n')
    parrafos = []
    contador = 1
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        # Intentar extraer número de párrafo si empieza con número y espacio/punto
        match = re.match(r'^(\d+)(?:\.|\s+|\))', bloque)
        if match:
            num = int(match.group(1))
            # Eliminar el número del inicio del contenido
            contenido = re.sub(r'^\d+(?:\.|\s+|\))', '', bloque).strip()
        else:
            num = contador
            contenido = bloque
            contador += 1
        
        # Limitar longitud
        if len(contenido) > TAMANO_MAX_PARRAFO:
            contenido = contenido[:TAMANO_MAX_PARRAFO]
        
        parrafos.append((num, contenido))
    return parrafos

def extraer_titulo_libro(texto_limpio, nombre_archivo, codigo):
    """Extrae el título real: primera línea no vacía que no sea código ni basura."""
    lineas = texto_limpio.split('\n')
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        # Ignorar líneas que parecen código o basura
        if re.match(r'^SPN\d{2}-\d{4}', linea, re.IGNORECASE):
            continue
        if len(linea) > 5 and len(linea) < 100:
            # Limpiar posibles residuos de Markdown en el título
            limpio = re.sub(r'[#*_`]', '', linea).strip()
            if limpio and not re.search(r'(copyright|derechos|www)', limpio, re.IGNORECASE):
                return limpio.upper()
    # Fallback: del nombre del archivo
    titulo = re.sub(r'^' + re.escape(codigo) + r'\s*', '', nombre_archivo)
    titulo = titulo.replace('_', ' ').replace('VGR', '').strip().upper()
    return titulo

def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    nombre_archivo = Path(ruta_pdf).stem
    
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else nombre_archivo.split()[0]
    
    # 1. Extraer con layout
    texto_raw = extraer_texto_estructurado(ruta_pdf)
    if not texto_raw:
        return 0
    
    # 2. Limpieza profunda (primera pasada para obtener título)
    # Hacemos una limpieza ligera solo para extraer título
    texto_para_titulo = limpieza_profunda(texto_raw)
    titulo_real = extraer_titulo_libro(texto_para_titulo, nombre_archivo, codigo)
    
    # 3. Limpieza definitiva usando el título para eliminar duplicados
    texto_limpio = limpieza_profunda(texto_raw, titulo_real)
    
    # 4. Insertar libro en BD (el título visible en la lista de libros será solo el código)
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (codigo, codigo, '2025'))   # título = solo código para la lista
    libro_id = cur.lastrowid
    conn.commit()
    
    # 5. Dividir en párrafos
    parrafos = dividir_en_parrafos(texto_limpio)
    
    # 6. Guardar párrafos
    total = 0
    for num_par, contenido in parrafos:
        # Limpiar el contenido de símbolos Markdown residuales (sin tocar corchetes/puntos)
        contenido = re.sub(r'[#*_`]', '', contenido)
        cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                    (libro_id, num_par, contenido))
        total += 1
        if total % 100 == 0:
            conn.commit()
    conn.commit()
    
    log(f"  -> {total} párrafos. Título real: {titulo_real}")
    return total

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