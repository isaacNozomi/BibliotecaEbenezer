import fitz
import sqlite3
import os
import re
from pathlib import Path
from collections import defaultdict

# ================= CONFIGURACIÓN =================
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
TAMANO_MAX_PARRAFO = 10000
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

# ================= LIMPIEZA DE TEXTO (SIN ROMPER CORCHETES) =================
def limpiar_basura_absoluta(texto):
    """Elimina solo caracteres de control, no toca corchetes ni signos normales."""
    if not texto:
        return ""
    # Eliminar caracteres de control excepto saltos de línea y tabuladores
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    # Normalizar espacios múltiples (deja uno)
    texto = re.sub(r'[ \t]+', ' ', texto)
    # Eliminar saltos de línea excesivos
    texto = re.sub(r'\n\s*\n', '\n\n', texto)
    return texto.strip()

# ================= DETECCIÓN POR POSICIÓN =================
def es_numero_pagina(rect, page_height):
    """Detecta si un bloque es número de página (centrado, parte inferior o superior)."""
    x0, y0, x1, y1 = rect
    ancho_pagina = 595  # aprox A4, pero usaremos relación
    # Centro horizontal (margen amplio)
    centro = (x0 + x1) / 2
    if not (ancho_pagina*0.4 < centro < ancho_pagina*0.6):
        return False
    # Posición vertical: en el 5% superior o 5% inferior
    if y1 < page_height * 0.1 or y0 > page_height * 0.9:
        return True
    return False

def es_encabezado_pie(texto, rect, page_height):
    """Detecta si el bloque es encabezado repetitivo como 'LA PALABRA HABLADA'."""
    texto_limpio = texto.strip()
    if not texto_limpio:
        return False
    # Palabras clave de encabezado
    if re.search(r'^LA\s+PALABRA\s+HABLADA', texto_limpio, re.IGNORECASE):
        return True
    # Posición en la parte superior (primer 10% de la página)
    if rect[3] < page_height * 0.1:
        return True
    return False

def extraer_parrafos_con_coordenadas(pagina):
    """
    Devuelve una lista de (numero_parrafo, texto) basado en análisis espacial.
    Para páginas sin numeración, numero_parrafo = 0 (luego se asignará contador).
    """
    page_height = pagina.rect.height
    # Obtener bloques de texto con información de posición
    bloques = pagina.get_text("dict")["blocks"]
    lineas_por_y = defaultdict(list)
    
    for bloque in bloques:
        if "lines" not in bloque:
            continue
        for linea in bloque["lines"]:
            for span in linea["spans"]:
                texto = span["text"].strip()
                if not texto:
                    continue
                rect = span["bbox"]
                y0 = rect[1]
                # Clasificar: si es número de página o encabezado, ignorar
                if es_numero_pagina(rect, page_height) or es_encabezado_pie(texto, rect, page_height):
                    continue
                # Guardar por coordenada Y (aproximada)
                lineas_por_y[round(y0, 1)].append((rect[0], texto))
    
    # Ordenar por Y descendente (arriba a abajo)
    y_ordenadas = sorted(lineas_por_y.keys())
    parrafos = []
    parrafo_actual = []
    ultimo_y = None
    ESPACIO_VERTICAL_MAX = 15  # puntos de separación entre párrafos
    
    for y in y_ordenadas:
        # Ordenar líneas en esta Y por X (izquierda a derecha)
        lineas = sorted(lineas_por_y[y], key=lambda x: x[0])
        texto_linea = " ".join([txt for _, txt in lineas])
        
        if ultimo_y is None or (y - ultimo_y) > ESPACIO_VERTICAL_MAX:
            # Nuevo párrafo
            if parrafo_actual:
                texto_parrafo = " ".join(parrafo_actual)
                # Detectar número de párrafo al inicio
                match = re.match(r'^\s*(\d+)(?:\.|\s+)', texto_parrafo)
                if match:
                    numero = int(match.group(1))
                    contenido = re.sub(r'^\s*\d+(?:\.|\s+)', '', texto_parrafo).strip()
                    parrafos.append((numero, contenido))
                else:
                    parrafos.append((0, texto_parrafo))  # 0 = sin número
                parrafo_actual = []
        parrafo_actual.append(texto_linea)
        ultimo_y = y
    
    # Último párrafo
    if parrafo_actual:
        texto_parrafo = " ".join(parrafo_actual)
        match = re.match(r'^\s*(\d+)(?:\.|\s+)', texto_parrafo)
        if match:
            numero = int(match.group(1))
            contenido = re.sub(r'^\s*\d+(?:\.|\s+)', '', texto_parrafo).strip()
            parrafos.append((numero, contenido))
        else:
            parrafos.append((0, texto_parrafo))
    
    return parrafos

# ================= DETECCIÓN DE TÍTULO DEL LIBRO =================
def extraer_titulo_libro(doc):
    """Extrae el título real del libro mirando primeras páginas y metadatos."""
    # Intentar con metadatos
    meta = doc.metadata
    if meta.get("title"):
        titulo = meta["title"].strip()
        if titulo and len(titulo) > 5:
            return titulo.upper()
    
    # Leer primeras 3 páginas completas (sin filtrar posición)
    texto_inicial = ""
    for i in range(min(3, len(doc))):
        texto_inicial += doc[i].get_text()
    
    # Buscar línea en mayúsculas de longitud razonable, no demasiado larga
    lineas = texto_inicial.split('\n')
    candidatos = []
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        # Título típico: entre 20 y 100 caracteres, mayúsculas, sin códigos SPN
        if 20 < len(linea) < 100 and linea.isupper() and not re.search(r'SPN\d{2}-\d{4}', linea):
            # Evitar falsos positivos (derechos, etc.)
            if not re.search(r'DERECHOS|RESERVADOS|COPYRIGHT|P\.O\.|BOX|www\.', linea, re.IGNORECASE):
                candidatos.append(linea)
    
    if candidatos:
        # Tomar el primero (suele ser el título principal)
        return candidatos[0].title()  # Formato bonito
    
    # Fallback: usar nombre del archivo limpio
    return None

# ================= PROCESAR UN PDF =================
def procesar_pdf(conn, ruta_pdf):
    log(f"Procesando: {ruta_pdf}")
    doc = fitz.open(ruta_pdf)
    
    # Obtener título real
    titulo_real = extraer_titulo_libro(doc)
    nombre_archivo = Path(ruta_pdf).stem
    codigo_match = re.search(r'(SPN\d{2}-\d{4})', nombre_archivo)
    codigo = codigo_match.group(1) if codigo_match else nombre_archivo.split()[0]
    
    if not titulo_real:
        # Limpiar nombre: quitar código, guiones bajos, extensión
        titulo_real = re.sub(r'^SPN\d{2}-\d{4}\s*', '', nombre_archivo)
        titulo_real = titulo_real.replace('_', ' ').replace('VGR', '').strip().upper()
    else:
        # Asegurar mayúsculas
        titulo_real = titulo_real.upper()
    
    # Insertar libro en BD
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)",
                (f"{codigo} {titulo_real}", codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()
    
    total_parrafos = 0
    parrafo_contador = 1  # para párrafos sin numeración
    
    for pagina_num in range(len(doc)):
        pagina = doc[pagina_num]
        parrafos_pagina = extraer_parrafos_con_coordenadas(pagina)
        
        for num_original, contenido in parrafos_pagina:
            if not contenido:
                continue
            
            # Limpiar basura absoluta (controles, etc.) sin dañar corchetes
            contenido = limpiar_basura_absoluta(contenido)
            if len(contenido) > TAMANO_MAX_PARRAFO:
                contenido = contenido[:TAMANO_MAX_PARRAFO]
            
            # Si el párrafo tiene número original (mayor que 0), usarlo, sino usar contador
            num_final = num_original if num_original > 0 else parrafo_contador
            
            # Guardar
            cur.execute("INSERT INTO parrafos (libro_id, numero_parrafo, contenido) VALUES (?, ?, ?)",
                        (libro_id, num_final, contenido))
            total_parrafos += 1
            if total_parrafos % 100 == 0:
                conn.commit()
            
            if num_original == 0:
                parrafo_contador += 1
        
        conn.commit()
    
    doc.close()
    log(f"Libro '{codigo} {titulo_real}' -> {total_parrafos} párrafos")
    return total_parrafos

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

# ================= PRINCIPAL =================
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
    log(f"Procesamiento completado. Total párrafos: {total_general}")
    print("Base de datos generada exitosamente.")

if __name__ == "__main__":
    procesar()