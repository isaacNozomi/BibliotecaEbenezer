import fitz
import sqlite3
import os
import re
from pathlib import Path

# Configuración
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"
TAMANO_MAX_PARRAFO = 2000  # caracteres máximos por párrafo (ajustable)
DEBUG = True  # Muestra logs detallados

def log(msg):
    if DEBUG:
        print(f"[INFO] {msg}")

def limpiar_texto(texto):
    """Limpia el texto eliminando caracteres no deseados y normalizando espacios."""
    if not texto:
        return ""
    # Eliminar caracteres de control (excepto saltos de línea y tabuladores)
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    # Reemplazar múltiples saltos de línea por un solo (para preservar párrafos)
    texto = re.sub(r'\n\s*\n', '\n\n', texto)
    # Reemplazar múltiples espacios por uno solo
    texto = re.sub(r'[ \t]+', ' ', texto)
    # Eliminar espacios al inicio y final
    texto = texto.strip()
    return texto

def es_linea_basura(linea):
    """Detecta líneas que son números de página, encabezados repetitivos o pies."""
    linea_limpia = linea.strip()
    if not linea_limpia:
        return False
    # Números de página solos (ej: "1", "2", " 3 ")
    if re.match(r'^\s*\d+\s*$', linea_limpia):
        return True
    # Frases comunes de encabezado/pie (personalizar según necesidad)
    patrones_basura = [
        r'^===== Page \d+ =====$',
        r'^LAS SIETE EDADES DE LA IGLESIA$',
        r'^William Marrion Branham$',
        r'^www\.branham\.org$',
        r'^P\.O\. Box \d+',
        r'^Todos los derechos reservados\.',
        r'^GRABACIONES “LA VOZ DE DIOS”',
        r'^Nota Sobre Los Derechos de Autor',
        r'^Para obtener mayores informes',
        r'^Voice of God Recordings',
        r'^SPANISH',
        r'^Existen más de \d+ sermones',
    ]
    for patron in patrones_basura:
        if re.search(patron, linea_limpia, re.IGNORECASE):
            return True
    return False

def extraer_parrafos_inteligente(texto_pagina):
    """
    Divide el texto en párrafos lógicos.
    Estrategia: primero dividir por doble salto de línea,
    luego por puntos seguidos de mayúscula cuando sea necesario.
    """
    if not texto_pagina:
        return []
    
    # Dividir por doble salto de línea (párrafos típicos)
    bloques = re.split(r'\n\s*\n', texto_pagina)
    parrafos = []
    
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        
        # Si el bloque es muy largo, intentar dividir por oraciones (punto + espacio + mayúscula)
        if len(bloque) > TAMANO_MAX_PARRAFO:
            # Dividir por punto seguido de espacio y mayúscula, pero conservando el punto
            oraciones = re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ])', bloque)
            parrafo_actual = []
            longitud_actual = 0
            for oracion in oraciones:
                if longitud_actual + len(oracion) < TAMANO_MAX_PARRAFO:
                    parrafo_actual.append(oracion)
                    longitud_actual += len(oracion)
                else:
                    if parrafo_actual:
                        parrafos.append(' '.join(parrafo_actual))
                    parrafo_actual = [oracion]
                    longitud_actual = len(oracion)
            if parrafo_actual:
                parrafos.append(' '.join(parrafo_actual))
        else:
            parrafos.append(bloque)
    
    return parrafos

def limpiar_pagina(texto_pagina):
    """Limpia una página completa eliminando líneas basura y normalizando."""
    lineas = texto_pagina.split('\n')
    lineas_limpias = []
    i = 0
    while i < len(lineas):
        linea = lineas[i].rstrip()
        # Si la línea termina con guión y la siguiente existe, unirlas
        if linea.endswith('-') and i+1 < len(lineas):
            siguiente = lineas[i+1].lstrip()
            linea = linea.rstrip('-') + siguiente
            i += 1  # saltar la siguiente línea porque ya la unimos
        if not es_linea_basura(linea):
            lineas_limpias.append(linea)
        i += 1
    
    texto_unido = ' '.join(lineas_limpias)
    # Reemplazar guiones silábicos que pudieran haber quedado
    texto_unido = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', texto_unido)
    return limpiar_texto(texto_unido)

def inicializar_db():
    """Crea las tablas y triggers si no existen."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Eliminar tablas existentes para regenerar (opcional, pero recomendado)
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
    # Triggers para mantener FTS sincronizado
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

def procesar_pdf(conn, ruta_pdf):
    """Procesa un solo PDF, extrayendo párrafos y guardándolos en BD."""
    log(f"Procesando: {ruta_pdf}")
    doc = fitz.open(ruta_pdf)
    titulo = Path(ruta_pdf).stem  # nombre sin extensión
    codigo = titulo.split(' ')[0] if titulo else "LIB"
    
    # Insertar libro
    cur = conn.cursor()
    cur.execute("INSERT INTO libros (titulo, codigo, fecha) VALUES (?, ?, ?)", 
                (titulo, codigo, '2025'))
    libro_id = cur.lastrowid
    conn.commit()
    
    numero_parrafo = 1
    total_parrafos = 0
    
    # Procesar página por página
    for num_pagina in range(len(doc)):
        pagina = doc[num_pagina]
        texto_raw = pagina.get_text()
        texto_limpio_pagina = limpiar_pagina(texto_raw)
        if not texto_limpio_pagina:
            continue
        
        parrafos = extraer_parrafos_inteligente(texto_limpio_pagina)
        
        for parrafo in parrafos:
            if not parrafo:
                continue
            # Limitar tamaño para evitar problemas en FTS5
            if len(parrafo) > 10000:
                log(f"Párrafo muy largo ({len(parrafo)} chars), truncando...")
                parrafo = parrafo[:10000]
            cur.execute("""
                INSERT INTO parrafos (libro_id, numero_parrafo, contenido)
                VALUES (?, ?, ?)
            """, (libro_id, numero_parrafo, parrafo))
            numero_parrafo += 1
            total_parrafos += 1
            # Commit cada 100 párrafos para no saturar la memoria
            if total_parrafos % 100 == 0:
                conn.commit()
        
        # Commit por página
        conn.commit()
    
    doc.close()
    log(f"Libro '{titulo}' procesado: {total_parrafos} párrafos insertados.")
    return total_parrafos

def procesar():
    """Función principal: procesa todos los PDFs en la carpeta."""
    conn = inicializar_db()
    archivos_pdf = [f for f in os.listdir(CARPETA_PDFS) if f.lower().endswith('.pdf')]
    if not archivos_pdf:
        log(f"No se encontraron archivos PDF en la carpeta '{CARPETA_PDFS}'")
        conn.close()
        return
    
    total_general = 0
    for archivo in archivos_pdf:
        ruta_completa = os.path.join(CARPETA_PDFS, archivo)
        try:
            num = procesar_pdf(conn, ruta_completa)
            total_general += num
        except Exception as e:
            log(f"Error procesando {archivo}: {e}")
            # Continuar con el siguiente archivo
            continue
    
    conn.commit()
    # Optimizar la base de datos (vacuum) después de insertar muchos datos
    log("Optimizando base de datos...")
    conn.execute("VACUUM")
    conn.close()
    log(f"Procesamiento completado. Total de párrafos insertados: {total_general}")
    print("Base de datos generada con FTS5 activado y limpieza de texto mejorada.")

if __name__ == "__main__":
    procesar()