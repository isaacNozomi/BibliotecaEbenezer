import fitz
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

# ================= LIMPIEZA AVANZADA =================
def limpiar_caracteres_extraños(texto):
    """Elimina caracteres raros (^?^, %&), etc.) y normaliza."""
    if not texto:
        return ""
    # Eliminar caracteres de control
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    # Eliminar patrones comunes de basura: ^?^, %&), ), etc. sueltos
    texto = re.sub(r'\^[?^]+\^', '', texto)
    texto = re.sub(r'[%&)(]+', '', texto)
    texto = re.sub(r'[^\w\sáéíóúüñÁÉÍÓÚÜÑ.,;:¿?¡!\"\'\-]', '', texto)
    # Reemplazar múltiples espacios y saltos
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n\s*\n', '\n\n', texto)
    return texto.strip()

def es_linea_basura(linea):
    """Detecta líneas que deben eliminarse por completo."""
    linea_limpia = linea.strip()
    if not linea_limpia:
        return True
    # Números de página solos
    if re.match(r'^\s*\d+\s*$', linea_limpia):
        return True
    # Encabezados/pies comunes
    patrones = [
        r'^===== Page \d+ =====$',
        r'^LAS SIETE EDADES DE LA IGLESIA$',
        r'^William Marrion Branham$',
        r'^www\.branham\.org$',
        r'^P\.O\. Box \d+',
        r'^Todos los derechos reservados\.',
        r'^GRABACIONES “LA VOZ DE DIOS”',
        r'^Nota Sobre Los Derechos de Autor',
        r'^Voice of God Recordings',
        r'^SPANISH',
        r'^Existen más de \d+ sermones',
        r'^©20\d{2} VGR',
        r'^Este Mensaje por el Hermano',
        r'^SPN\d{2}-\d{4}',
        r'^LA PALABRA HABLADA',
        r'^LA\s+PALABRA\s+HABLADA',
        r'^\d+\s+LA PALABRA HABLADA',
    ]
    for pat in patrones:
        if re.search(pat, linea_limpia, re.IGNORECASE):
            return True
    return False

def extraer_titulo_inteligente(doc):
    """Detecta el título real del libro desde las primeras páginas."""
    texto_inicial = ""
    for i in range(min(5, len(doc))):
        texto_inicial += doc[i].get_text()
    lineas = texto_inicial.split('\n')
    # Buscar una línea que parezca título: mayúsculas, longitud entre 10 y 100, no contenga código
    for linea in lineas:
        linea = linea.strip()
        if 10 < len(linea) < 100 and linea.isupper() and not re.search(r'SPN\d{2}-\d{4}', linea):
            # Evitar falsos positivos como "TODOS LOS DERECHOS RESERVADOS"
            if not re.search(r'DERECHOS|RESERVADOS|COPYRIGHT', linea, re.IGNORECASE):
                return linea.title()
    # Si no, buscar después del código en el nombre del archivo (como respaldo)
    return None

def tiene_parrafos_numerados(texto):
    """Detecta si el texto usa numeración de párrafos."""
    for linea in texto.split('\n')[:100]:
        if re.match(r'^\s*\d+\s+[A-ZÁÉÍÓÚÜÑ]', linea):
            return True
        if re.match(r'^\s*\d+\.\s+[A-ZÁÉÍÓÚÜÑ]', linea):
            return True
        if re.match(r'^\s*§\s*\d+', linea):
            return True
    return False

def extraer_parrafos_numerados(texto_completo):
    """Extrae párrafos con formato: 1 contenido... 2 contenido... (respeta números)"""
    # Soporta: "1 texto", "1. texto", "§ 1 texto", "1) texto"
    patrones = [
        r'\n\s*(\d+)\s+(.+?)(?=\n\s*\d+\s+|\Z)',
        r'\n\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.\s+|\Z)',
        r'\n\s*§\s*(\d+)\s+(.+?)(?=\n\s*§\s*\d+|\Z)',
        r'\n\s*(\d+)\)\s+(.+?)(?=\n\s*\d+\)\s+|\Z)'
    ]
    for patron in patrones:
        matches = re.findall(patron, texto_completo, re.DOTALL)
        if matches:
            resultados = []
            for num, cont in matches:
                cont = limpiar_caracteres_extraños(cont)
                if cont:
                    resultados.append((int(num), cont))
            return resultados
    return []

def extraer_parrafos_no_numerados(texto_pagina):
    """Divide por doble salto de línea."""
    bloques = re.split(r'\n\s*\n', texto_pagina)
    parrafos = []
    for bloque in bloques:
        bloque = limpiar_caracteres_extraños(bloque)
        if not bloque:
            continue
        if len(bloque) > TAMANO_MAX_PARRAFO:
            # dividir en oraciones
            oraciones = re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ])', bloque)
            for oracion in oraciones:
                if oracion.strip():
                    parrafos.append(oracion.strip())
        else:
            parrafos.append(bloque)
    return parrafos

def limpiar_pagina(texto_pagina):
    """Elimina líneas basura y une palabras cortadas."""
    lineas = texto_pagina.split('\n')
    lineas_limpias = []
    i = 0
    while i < len(lineas):
        linea = lineas[i].rstrip()
        # Unir palabras con guión al final
        if linea.endswith('-') and i+1 < len(lineas):
            siguiente = lineas[i+1].lstrip()
            linea = linea.rstrip('-') + siguiente
            i += 1
        if not es_linea_basura(linea):
            lineas_limpias.append(linea)
        i += 1
    texto_unido = ' '.join(lineas_limpias)
    texto_unido = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', texto_unido)
    return limpiar_caracteres_extraños(texto_unido)

# ================= BASE DE DATOS =================
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

# ================= PROCESAR UN PDF =================
def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    doc = fitz.open(ruta_pdf)
    
    # 1. Extraer título inteligente
    titulo_real = extraer_titulo_inteligente(doc)
    nombre_archivo = Path(ruta_pdf).stem
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else nombre_archivo.split()[0]
    
    if not titulo_real:
        # Limpiar nombre del archivo: quitar código, guiones bajos, etc.
        titulo_real = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre_archivo)
        titulo_real = titulo_real.replace('_', ' ').replace('VGR', '').strip().title()
    
    # 2. Insertar libro
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_real, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()
    
    # 3. Recopilar todo el texto para análisis
    texto_completo = ""
    for num_pag in range(len(doc)):
        texto_completo += doc[num_pag].get_text() + "\n"
    
    tiene_numeracion = tiene_parrafos_numerados(texto_completo)
    log(f"¿Tiene numeración? {tiene_numeracion}")
    
    total_parrafos = 0
    
    if tiene_numeracion:
        parrafos_num = extraer_parrafos_numerados(texto_completo)
        for num_orig, contenido in parrafos_num:
            # Limpiar longitud
            if len(contenido) > TAMANO_MAX_PARRAFO:
                contenido = contenido[:TAMANO_MAX_PARRAFO]
            cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                        (libro_id, num_orig, contenido))
            total_parrafos += 1
            if total_parrafos % 100 == 0:
                conn.commit()
    else:
        num_parrafo = 1
        for num_pag in range(len(doc)):
            texto_raw = doc[num_pag].get_text()
            texto_limpio = limpiar_pagina(texto_raw)
            if not texto_limpio:
                continue
            parrafos = extraer_parrafos_no_numerados(texto_limpio)
            for p in parrafos:
                if not p:
                    continue
                if len(p) > TAMANO_MAX_PARRAFO:
                    p = p[:TAMANO_MAX_PARRAFO]
                cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                            (libro_id, num_parrafo, p))
                num_parrafo += 1
                total_parrafos += 1
                if total_parrafos % 100 == 0:
                    conn.commit()
            conn.commit()
    
    doc.close()
    log(f"Libro '{titulo_real}' -> {total_parrafos} párrafos")
    return total_parrafos

# ================= PRINCIPAL =================
def procesar():
    conn = inicializar_db()
    archivos = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith('.pdf')]
    if not archivos:
        log(f"No hay PDFs en '{CARPETA_PDFS}'")
        conn.close()
        return
    total = 0
    for arch in archivos:
        ruta = os.path.join(CARPETA_PDFS, arch)
        try:
            total += procesar_pdf(conn, ruta)
        except Exception as e:
            log(f"Error en {arch}: {e}")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    log(f"FIN: {total} párrafos insertados")

if __name__ == "__main__":
    procesar()