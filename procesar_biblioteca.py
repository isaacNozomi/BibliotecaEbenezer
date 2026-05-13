import fitz  # PyMuPDF
import sqlite3
import os
import re

# CONFIGURACIÓN
CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"

def inicializar_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Borrar tablas anteriores (opcional, útil para regeneraciones)
    cursor.execute("DROP TABLE IF EXISTS libros")
    cursor.execute("DROP TABLE IF EXISTS parrafos")
    cursor.execute("DROP TABLE IF EXISTS parrafos_fts")
    cursor.execute("DROP TABLE IF EXISTS room_master_table")  # Por si acaso
    
    # Crear libros con las columnas exactas de LibroEntity
    cursor.execute("""
        CREATE TABLE libros (
            id INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            codigo TEXT NOT NULL,
            fecha TEXT NOT NULL DEFAULT ''
        )
    """)
    
    # Crear párrafos con las columnas exactas de ParrafoEntity
    cursor.execute("""
        CREATE TABLE parrafos (
            id INTEGER PRIMARY KEY,
            libro_id INTEGER NOT NULL,
            numero_parrafo INTEGER NOT NULL,
            contenido TEXT NOT NULL,
            FOREIGN KEY(libro_id) REFERENCES libros(id) ON DELETE CASCADE
        )
    """)
    
    # Crear tabla virtual FTS5 (contenido sincronizado con parrafos)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS parrafos_fts USING fts5(
            contenido,
            content=parrafos,
            content_rowid=id,
            tokenize='unicode61'
        )
    """)
    
    # Disparadores para mantener sincronizada la tabla FTS automáticamente
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS parrafos_ai AFTER INSERT ON parrafos BEGIN
            INSERT INTO parrafos_fts(rowid, contenido) VALUES (new.id, new.contenido);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS parrafos_ad AFTER DELETE ON parrafos BEGIN
            INSERT INTO parrafos_fts(parrafos_fts, rowid, contenido) VALUES('delete', old.id, old.contenido);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS parrafos_au AFTER UPDATE ON parrafos BEGIN
            INSERT INTO parrafos_fts(parrafos_fts, rowid, contenido) VALUES('delete', old.id, old.contenido);
            INSERT INTO parrafos_fts(rowid, contenido) VALUES (new.id, new.contenido);
        END
    """)
    
    conn.commit()
    return conn

def extraer_parrafos(texto_completo):
    # Tu lógica de extracción se mantiene igual si funciona con tus PDFs
    bloques = re.split(r'\n\s*(\d+)\s*\n', texto_completo)
    resultado = []
    for i in range(1, len(bloques), 2):
        num_parrafo = int(bloques[i])
        contenido = bloques[i+1].strip().replace('\r', '')
        if contenido:
            resultado.append((num_parrafo, contenido))
    return resultado

def procesar():
    if not os.path.exists(CARPETA_PDFS):
        print(f"Error: Crea la carpeta '{CARPETA_PDFS}' y pon tus PDFs allí.")
        return

    conn = inicializar_db()
    cursor = conn.cursor()
    
    archivos = [f for f in os.listdir(CARPETA_PDFS) if f.endswith('.pdf')]
    print(f"Detectados {len(archivos)} libros. Empezando proceso...")

    for nombre_archivo in archivos:
        path_completo = os.path.join(CARPETA_PDFS, nombre_archivo)
        doc = fitz.open(path_completo)
        
        titulo = nombre_archivo.replace('.pdf', '')
        codigo = titulo.split(' ')[0]  # o la lógica que prefieras
        
        # Insertar libro con fecha genérica (puedes cambiarlo)
        cursor.execute(
            "INSERT INTO libros (id, titulo, codigo, fecha) VALUES (?, ?, ?, ?)",
            (None, titulo, codigo, "2025")
        )
        libro_id = cursor.lastrowid
        
        # Extraer texto completo
        texto_total = ""
        for pagina in doc:
            texto_total += pagina.get_text()
        
        parrafos = extraer_parrafos(texto_total)
        
        # Insertar párrafos en bloque (los triggers llenarán parrafos_fts)
        datos = [(None, libro_id, num, cont) for num, cont in parrafos]
        cursor.executemany(
            "INSERT INTO parrafos (id, libro_id, numero_parrafo, contenido) VALUES (?, ?, ?, ?)",
            datos
        )
        
        print(f"✔ Procesado: {titulo} ({len(parrafos)} párrafos)")
        doc.close()

    conn.commit()
    conn.close()
    print(f"\n¡ÉXITO! Base de datos generada en: {DB_PATH}")

if __name__ == "__main__":
    procesar()