import fitz
import sqlite3
import os
import re
from pathlib import Path

# Configuración
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
TAMANO_MAX_PARRAFO = 10000  # caracteres máximos por párrafo
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

def limpiar_texto(texto):
    """Limpia caracteres de control y normaliza espacios."""
    if not texto:
        return ""
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    texto = re.sub(r'\n\s*\n', '\n\n', texto)
    texto = re.sub(r'[ \t]+', ' ', texto)
    return texto.strip()

def es_linea_basura(linea):
    """Detecta líneas que deben eliminarse (páginas, derechos de autor, etc.)"""
    linea_limpia = linea.strip()
    if not linea_limpia:
        return False
    if re.match(r'^\s*\d+\s*$', linea_limpia):  # números de página solos
        return True
    patrones_basura = [
        r'^===== Page \d+ =====$', r'^LAS SIETE EDADES DE LA IGLESIA$',
        r'^William Marrion Branham$', r'^www\.branham\.org$', r'^P\.O\. Box \d+',
        r'^Todos los derechos reservados\.', r'^GRABACIONES “LA VOZ DE DIOS”',
        r'^Nota Sobre Los Derechos de Autor', r'^Voice of God Recordings',
        r'^SPANISH', r'^Existen más de \d+ sermones', r'^©20\d{2} VGR',
        r'^Este Mensaje por el Hermano', r'^SPN\d{2}-\d{4}'
    ]
    for patron in patrones_basura:
        if re.search(patron, linea_limpia, re.IGNORECASE):
            return True
    return False

def extraer_titulo_desde_pdf(doc):
    """
    Intenta extraer el título real del libro desde las primeras páginas.
    Busca patrones como "UNA EXPOSICIÓN DE LAS SIETE EDADES", etc.
    """
    texto_primeras_paginas = ""
    for i in range(min(5, len(doc))):
        texto_primeras_paginas += doc[i].get_text()
    
    # Patrones de títulos en español (ajústalos según tus libros)
    patrones_titulo = [
        r'UNA EXPOSICIÓN DE LAS SIETE EDADES DE LA IGLESIA',
        r'La Deidad De Jesucristo',
        r'Fe Es La Sustancia',
        r'Los Principios De La Sanidad Divina',
        r'Creyendo A Dios',
        r'Mi Ángel Irá Delante De Ti',
        r'Un Filtro Para Hombres Pensantes'
    ]
    for patron in patrones_titulo:
        match = re.search(patron, texto_primeras_paginas, re.IGNORECASE)
        if match:
            return match.group(0).title()  # devuelve el título encontrado
    # Si no se encuentra, usar el nombre del archivo (pero limpiando código)
    return None

def tiene_parrafos_numerados(texto_muestra):
    """
    Detecta si el PDF usa numeración de párrafos estilo "1 texto..." o "1. texto..."
    """
    lineas = texto_muestra.split('\n')
    for linea in lineas[:100]:  # analizar primeras 100 líneas
        if re.match(r'^\s*\d+\s+[A-ZÁÉÍÓÚÜÑ]', linea):
            return True
        if re.match(r'^\s*\d+\.\s+[A-ZÁÉÍÓÚÜÑ]', linea):
            return True
    return False

def extraer_parrafos_numerados(texto_completo):
    """
    Extrae párrafos numerados del tipo:
    1 Este es el contenido...
    2 Otro párrafo...
    Devuelve lista de (numero, contenido)
    """
    patron = r'\n\s*(\d+)\s+(.+?)(?=\n\s*\d+\s+|\Z)'
    matches = re.findall(patron, texto_completo, re.DOTALL)
    if not matches:
        # Intentar con formato "1. "
        patron2 = r'\n\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.\s+|\Z)'
        matches = re.findall(patron2, texto_completo, re.DOTALL)
    
    resultados = []
    for num, cont in matches:
        cont = limpiar_texto(cont)
        if cont:
            resultados.append((int(num), cont))
    return resultados

def extraer_parrafos_no_numerados(texto_pagina):
    """Divide el texto en párrafos por doble salto de línea, sin números."""
    bloques = re.split(r'\n\s*\n', texto_pagina)
    parrafos = []
    for bloque in bloques:
        bloque = bloque.strip()
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
    """Elimina líneas basura y une palabras cortadas por guión."""
    lineas = texto_pagina.split('\n')
    lineas_limpias = []
    i = 0
    while i < len(lineas):
        linea = lineas[i].rstrip()
        # Unir palabras cortadas por guión
        if linea.endswith('-') and i+1 < len(lineas):
            siguiente = lineas[i+1].lstrip()
            linea = linea.rstrip('-') + siguiente
            i += 1
        if not es_linea_basura(linea):
            lineas_limpias.append(linea)
        i += 1
    texto_unido = ' '.join(lineas_limpias)
    texto_unido = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', texto_unido)
    return limpiar_texto(texto_unido)

def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    doc = fitz.open(ruta_pdf)
    
    # Extraer título real desde el contenido del PDF
    titulo_real = extraer_titulo_desde_pdf(doc)
    nombre_archivo = Path(ruta_pdf).stem
    # Extraer código (ej: SPN47-0412) del nombre del archivo
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else nombre_archivo.split()[0]
    
    # Si no se encontró título en español, usar el nombre del archivo sin el código
    if not titulo_real:
        titulo_real = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre_archivo).replace('_', ' ').title()
    
    # Insertar libro
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (titulo_real, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()
    
    # Recopilar todo el texto para decidir método de extracción
    texto_completo = ""
    for num_pag in range(len(doc)):
        texto_completo += doc[num_pag].get_text() + "\n"
    
    tiene_numeracion = tiene_parrafos_numerados(texto_completo)
    log(f"¿Tiene numeración de párrafos? {tiene_numeracion}")
    
    numero_parrafo_db = 1
    total_parrafos = 0
    
    if tiene_numeracion:
        # Extraer párrafos numerados
        parrafos_numerados = extraer_parrafos_numerados(texto_completo)
        for num_original, contenido in parrafos_numerados:
            if len(contenido) > TAMANO_MAX_PARRAFO:
                contenido = contenido[:TAMANO_MAX_PARRAFO]
            cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                        (libro_id, num_original, contenido))
            total_parrafos += 1
            if total_parrafos % 100 == 0:
                conn.commit()
    else:
        # Procesar página por página (sin numeración)
        for num_pagina in range(len(doc)):
            pagina = doc[num_pagina]
            texto_raw = pagina.get_text()
            texto_limpio = limpiar_pagina(texto_raw)
            if not texto_limpio:
                continue
            parrafos = extraer_parrafos_no_numerados(texto_limpio)
            for parrafo in parrafos:
                if not parrafo:
                    continue
                if len(parrafo) > TAMANO_MAX_PARRAFO:
                    parrafo = parrafo[:TAMANO_MAX_PARRAFO]
                cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                            (libro_id, numero_parrafo_db, parrafo))
                numero_parrafo_db += 1
                total_parrafos += 1
                if total_parrafos % 100 == 0:
                    conn.commit()
            conn.commit()
    
    doc.close()
    log(f"Libro '{titulo_real}' procesado: {total_parrafos} párrafos insertados.")
    return total_parrafos

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
    archivos_pdf = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith('.pdf')]
    if not archivos_pdf:
        log(f"No se encontraron PDFs en '{CARPETA_PDFS}'")
        conn.close()
        return
    total_general = 0
    for archivo in archivos_pdf:
        ruta = os.path.join(CARPETA_PDFS, archivo)
        try:
            total_general += procesar_pdf(conn, ruta)
        except Exception as e:
            log(f"Error con {archivo}: {e}")
    conn.commit()
    log("Optimizando BD...")
    conn.execute("VACUUM")
    conn.close()
    log(f"Procesamiento completado. Total párrafos: {total_general}")
    print("Base de datos generada exitosamente.")

if __name__ == "__main__":
    procesar()