import fitz
import sqlite3, os, re

CARPETA_PDFS = "mis_libros"
DB_PATH = "app/src/main/assets/database/biblioteca.db"

def inicializar_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS libros")
    cur.execute("DROP TABLE IF EXISTS parrafos")
    cur.execute("DROP TABLE IF EXISTS parrafos_fts")
    cur.execute("CREATE TABLE libros (id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, codigo TEXT NOT NULL, fecha TEXT NOT NULL DEFAULT '')")
    cur.execute("CREATE TABLE parrafos (id INTEGER PRIMARY KEY, libro_id INTEGER NOT NULL, numero_parrafo INTEGER NOT NULL, contenido TEXT NOT NULL, FOREIGN KEY(libro_id) REFERENCES libros(id) ON DELETE CASCADE)")
    cur.execute("CREATE VIRTUAL TABLE parrafos_fts USING fts5(contenido, content=parrafos, content_rowid=id, tokenize='unicode61')")
    cur.execute("CREATE TRIGGER IF NOT EXISTS parrafos_ai AFTER INSERT ON parrafos BEGIN INSERT INTO parrafos_fts(rowid, contenido) VALUES (new.id, new.contenido); END")
    cur.execute("CREATE TRIGGER IF NOT EXISTS parrafos_ad AFTER DELETE ON parrafos BEGIN INSERT INTO parrafos_fts(parrafos_fts, rowid, contenido) VALUES('delete', old.id, old.contenido); END")
    cur.execute("CREATE TRIGGER IF NOT EXISTS parrafos_au AFTER UPDATE ON parrafos BEGIN INSERT INTO parrafos_fts(parrafos_fts, rowid, contenido) VALUES('delete', old.id, old.contenido); INSERT INTO parrafos_fts(rowid, contenido) VALUES (new.id, new.contenido); END")
    conn.commit()
    return conn

def extraer_parrafos(texto):
    bloques = re.split(r'\n\s*(\d+)\s*\n', texto)
    resultado = []
    for i in range(1, len(bloques), 2):
        num = int(bloques[i])
        contenido = bloques[i+1].strip().replace('\r', '')
        if contenido:
            resultado.append((num, contenido))
    return resultado

def procesar():
    conn = inicializar_db()
    cur = conn.cursor()
    for archivo in [f for f in os.listdir(CARPETA_PDFS) if f.endswith('.pdf')]:
        doc = fitz.open(os.path.join(CARPETA_PDFS, archivo))
        titulo = archivo.replace('.pdf', '')
        codigo = titulo.split(' ')[0]
        cur.execute("INSERT INTO libros (id, titulo, codigo, fecha) VALUES (NULL, ?, ?, '2025')", (titulo, codigo))
        libro_id = cur.lastrowid
        texto_total = ""
        for pagina in doc:
            texto_total += pagina.get_text()
        for num, cont in extraer_parrafos(texto_total):
            cur.execute("INSERT INTO parrafos (id, libro_id, numero_parrafo, contenido) VALUES (NULL, ?, ?, ?)", (libro_id, num, cont))
        doc.close()
    conn.commit()
    conn.close()
    print("Base de datos generada con FTS5 activado.")

if __name__ == "__main__":
    procesar()