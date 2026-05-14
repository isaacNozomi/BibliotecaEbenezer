import fitz  # sigue siendo la base, pymupdf4llm usa fitz internamente
import pymupdf4llm
import sqlite3
import os
import re
from pathlib import Path

# ================= CONFIGURACIÓN =================
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
TAMANO_MAX_PARRAFO = 10000
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

# ================= FUNCIÓN QUE EXTRAE TEXTO LIMPIO CON LAYOUT =================
def extraer_texto_estructurado(ruta_pdf):
    """
    Usa pymupdf4llm con layout mode para obtener Markdown limpio.
    El layout mode automáticamente:
        - Detecta columnas y ordena el texto visualmente.
        - Clasifica encabezados, pies de página, párrafos normales.
        - Elimina números de página y elementos repetitivos.
    Devuelve el texto completo como string (en formato Markdown).
    """
    log("  -> Extrayendo con layout mode (detecta estructura visual)...")
    try:
        # El parámetro page_chunks=False devuelve todo el documento en un solo string
        md_text = pymupdf4llm.to_markdown(
            ruta_pdf,
            page_chunks=False,   # queremos todo junto
            write_images=False,   # no necesitamos imágenes
            use_llm=False         # no usar IA adicional, solo layout analysis
        )
        return md_text
    except Exception as e:
        log(f"  Error en layout: {e}")
        return None

# ================= LIMPIEZA FINA (elimina lo que el layout pueda dejar) =================
def limpieza_final(texto):
    """Elimina líneas sueltas de encabezados/pies que el layout no detectó."""
    if not texto:
        return ""
    lineas = texto.split('\n')
    lineas_limpias = []
    for linea in lineas:
        linea_limpia = linea.strip()
        # Eliminar números de página que hayan quedado (p.ej. "1", "2" solos)
        if re.match(r'^\d+$', linea_limpia):
            continue
        # Eliminar "LA PALABRA HABLADA" y variantes
        if re.search(r'^LA\s+PALABRA\s+HABLADA', linea_limpia, re.IGNORECASE):
            continue
        # Eliminar líneas con copyright o derechos reservados
        if re.search(r'(todos los derechos reservados|copyright|©|www\.branham)', linea_limpia, re.IGNORECASE):
            continue
        lineas_limpias.append(linea)
    return '\n'.join(lineas_limpias)

# ================= DIVIDIR EN PÁRRAFOS =================
def dividir_en_parrafos(texto_limpio):
    """
    Divide el texto por doble salto de línea (típico de Markdown).
    Devuelve lista de (numero_parrafo, contenido).
    Si detecta un número al inicio (1, 1., § 1), lo usa como número.
    """
    bloques = texto_limpio.split('\n\n')
    parrafos = []
    contador = 1
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        # Intentar extraer número de párrafo al inicio
        match = re.match(r'^\s*(\d+)(?:\.|\s+|$)', bloque)
        if match:
            num = int(match.group(1))
            contenido = re.sub(r'^\s*\d+(?:\.|\s+)', '', bloque).strip()
        else:
            # Párrafo sin número: asignamos un número correlativo
            num = contador
            contenido = bloque
            contador += 1
        # Limitar tamaño
        if len(contenido) > TAMANO_MAX_PARRAFO:
            contenido = contenido[:TAMANO_MAX_PARRAFO]
        parrafos.append((num, contenido))
    return parrafos

# ================= EXTRAER TÍTULO REAL DEL LIBRO =================
def extraer_titulo_libro(texto_estructurado, nombre_archivo, codigo):
    """
    Busca el título real dentro del texto estructurado.
    Prioriza: líneas que sean títulos (nivel 1 en Markdown: # Título)
    También busca líneas en mayúsculas de longitud adecuada.
    """
    # Buscar líneas que empiezan con "# " (título Markdown)
    for linea in texto_estructurado.split('\n'):
        if linea.startswith('# '):
            titulo = linea[2:].strip()
            if titulo and len(titulo) > 5:
                return titulo.upper()
    # Si no, buscar líneas en mayúsculas no muy largas
    for linea in texto_estructurado.split('\n'):
        linea = linea.strip()
        if 10 < len(linea) < 100 and linea.isupper():
            # Evitar falsos positivos
            if not re.search(r'DERECHOS|RESERVADOS|COPYRIGHT', linea, re.IGNORECASE):
                return linea.title()
    # Fallback: usar el nombre del archivo limpio (sin código)
    titulo = re.sub(r'^' + re.escape(codigo) + r'\s*', '', nombre_archivo)
    titulo = titulo.replace('_', ' ').replace('VGR', '').strip().upper()
    return titulo

# ================= PROCESAR UN PDF =================
def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    nombre_archivo = Path(ruta_pdf).stem
    
    # Extraer código del nombre (ej: SPN47-0412)
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else nombre_archivo.split()[0]
    
    # 1. Extraer texto estructurado con layout mode
    texto_estructurado = extraer_texto_estructurado(ruta_pdf)
    if not texto_estructurado:
        log("  ERROR: No se pudo extraer texto con layout, se omite.")
        return 0
    
    # 2. Limpieza final de restos
    texto_limpio = limpieza_final(texto_estructurado)
    
    # 3. Extraer título del libro
    titulo_real = extraer_titulo_libro(texto_limpio, nombre_archivo, codigo)
    titulo_formateado = f"{codigo} {titulo_real}"
    
    # 4. Insertar libro en BD
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_formateado, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()
    
    # 5. Dividir en párrafos
    parrafos = dividir_en_parrafos(texto_limpio)
    
    # 6. Guardar párrafos
    total = 0
    for num_par, contenido in parrafos:
        cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                    (libro_id, num_par, contenido))
        total += 1
        if total % 100 == 0:
            conn.commit()
    conn.commit()
    
    log(f"  -> {total} párrafos guardados. Título: {titulo_formateado}")
    return total

# ================= INICIALIZAR BASE DE DATOS =================
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
    # Triggers para FTS5
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