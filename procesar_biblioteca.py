import fitz  # PyMuPDF
import sqlite3
import os
import re

# CONFIGURACIÓN
CARPETA_PDFS = "mis_libros"  # Pon tus PDFs en una carpeta con este nombre
DB_PATH = "app/src/main/assets/database/biblioteca.db"

def inicializar_db():
    # Creamos la carpeta si no existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Creamos las tablas tal como las definimos en la App de Android
    cursor.execute("DROP TABLE IF EXISTS libros")
    cursor.execute("DROP TABLE IF EXISTS parrafos")
    
    cursor.execute("""
        CREATE TABLE libros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            codigo TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE parrafos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            libroId INTEGER,
            numero INTEGER,
            contenido TEXT,
            referenciaBiblica TEXT,
            FOREIGN KEY(libroId) REFERENCES libros(id)
        )
    """)
    
    # Room necesita una tabla técnica para funcionar
    cursor.execute("CREATE TABLE IF NOT EXISTS room_master_table (id INTEGER PRIMARY KEY,identity_hash TEXT)")
    cursor.execute("INSERT OR REPLACE INTO room_master_table (id,identity_hash) VALUES(42, '777')")
    
    conn.commit()
    return conn

def extraer_parrafos(texto_completo):
    # Esta expresión busca números de párrafo (ej: "\n 2 \n" o "\n15\n")
    # Es específica para el formato de los libros que me mostraste
    bloques = re.split(r'\n\s*(\d+)\s*\n', texto_completo)
    
    resultado = []
    # El primer elemento antes del primer número suele ser la introducción
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
        
        # El título es el nombre del archivo (quitando el .pdf)
        titulo = nombre_archivo.replace('.pdf', '')
        codigo = titulo.split(' ')[0] # Toma la primera palabra como código
        
        # Insertar libro
        cursor.execute("INSERT INTO libros (titulo, codigo) VALUES (?, ?)", (titulo, codigo))
        libro_id = cursor.lastrowid
        
        # Extraer todo el texto del libro
        texto_total = ""
        for pagina in doc:
            texto_total += pagina.get_text()
        
        # Procesar párrafos
        parrafos = extraer_parrafos(texto_total)
        
        # Insertar párrafos en masa (más rápido)
        datos_parrafos = [(libro_id, p[0], p[1]) for p in parrafos]
        cursor.executemany("INSERT INTO parrafos (libroId, numero, contenido) VALUES (?, ?, ?)", datos_parrafos)
        
        print(f"✔ Procesado: {titulo} ({len(parrafos)} párrafos)")
        doc.close()

    conn.commit()
    conn.close()
    print(f"\n¡ÉXITO! Base de datos generada en: {DB_PATH}")

if __name__ == "__main__":
    procesar()