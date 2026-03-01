from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import pdfplumber
import re
from collections import defaultdict
from datetime import datetime
from docx import Document
from flask import send_from_directory
from flask import session

app = Flask(__name__)
app.secret_key = "mi_clave_super_secreta_123"

@app.context_processor
def inject_user():
    return dict(session=session)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx", "jpg", "jpeg", "xls", "xlsx"}

def parse_pdf_date(pdf_date):
    # Formato típico: D:YYYYMMDDHHmmSSOHH'mm'
    match = re.search(r'D:(\d{4})(\d{2})(\d{2})', pdf_date)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return pdf_date  # fallback

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

STOPWORDS ={'a', 'acá', 'acá', 'acá', 'acá', 'ahí', 'ahí', 'ahí', 'al', 'algo', 'alguien', 'allá', 'allá', 'allá', 'allá', 'allí', 'allí', 'allí', 'allí', 'aquellos', 'aquél', 'aquélla', 'aquéllas', 'aquí', 'aquí', 'aquí', 'aquí', 'así',
            'como', 'con', 'conocer', 'creer', 'cualquier', 'cualquiera', 'cuando', 'cuál', 'cuándo', 'cuánto', 'cómo', 'dar', 'de', 'deber', 'decir', 'dejar', 'del', 'dijo', 'dónde', 'el', 'ella', 'ellas', 'ellas', 'ellos', 'ellos',
            'en', 'encontrar', 'encontró', 'entender', 'entre', 'era', 'era', 'es', 'esa', 'esas', 'escribir', 'ese', 'esos', 'estaba', 'estaban', 'estar', 'estaría', 'estaría', 'estaríais', 'estaríamos', 'estarían', 'estarías', 'este',
            'esto', 'estuve', 'estuvieron', 'estuvimos', 'estuviste', 'estuvisteis', 'estuvo', 'está', 'están', 'fue', 'ha', 'haber', 'hablar', 'había', 'hacer', 'hasta', 'hoy', 'ir', 'la', 'las', 'le', 'le', 'les', 'llamar', 'llegar',
            'llevar', 'lo', 'lo', 'los', 'me', 'mi', 'misma', 'mismas', 'mismo', 'mismos', 'muy', 'más', 'nada', 'nadie', 'no', 'nos', 'nosotros', 'nuestro', 'o', 'ocurrir', 'os', 'otra', 'otras', 'otro', 'otros', 'para', 'parecer', 'pasar',
            'pensar', 'perder', 'pero', 'poner', 'por', 'porque', 'producir', 'que', 'quedar', 'querer', 'quién', 'qué', 'qué', 'saber', 'salir', 'se', 'seguir', 'sentir', 'ser', 'si', 'si', 'sin', 'sobre', 'son', 'su', 'sus', 'sí', 'sí',
            'sólo', 'también', 'tan', 'tan', 'te', 'tener', 'toda', 'todo', 'tomar', 'trabajar', 'tu', 'tú', 'un', 'una', 'venir', 'ver', 'vez', 'vio', 'vio', 'vivir', 'volver', 'vosotros', 'vuestro', 'y', 'ya', 'yo', 'á', 'él'}

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT,
            fecha_subida TEXT,
            contenido TEXT,
            keywords TEXT,
            titulo TEXT,
            autor TEXT,
            fecha_creacion TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_nombre_archivo 
        ON documentos (nombre_archivo)
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

def preprocess(text):
    text = text.lower()
    words = re.findall(r'\b[a-záéíóúñ]+\b', text)
    return [w for w in words if w not in STOPWORDS]

def build_graph(words, window_size=4):
    graph = defaultdict(set)
    for i in range(len(words)):
        for j in range(i+1, min(i+window_size, len(words))):
            if words[i] != words[j]:
                graph[words[i]].add(words[j])
                graph[words[j]].add(words[i])
    return graph

def textrank(graph, d=0.85, max_iter=50):
    scores = {node: 1.0 for node in graph}
    for _ in range(max_iter):
        new_scores = {}
        for node in graph:
            rank_sum = 0
            for neighbor in graph[node]:
                if len(graph[neighbor]) > 0:
                    rank_sum += scores[neighbor] / len(graph[neighbor])
            new_scores[node] = (1 - d) + d * rank_sum
        scores = new_scores
    return scores

def extract_keywords(text, top_n=10):
    words = preprocess(text)
    if not words: return []
    graph = build_graph(words)
    scores = textrank(graph)
    sorted_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [w[0] for w in sorted_words[:top_n]]


@app.route("/")
def index():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre_archivo, fecha_subida, keywords FROM documentos ORDER BY id DESC")
    documentos = cursor.fetchall()
    conn.close()
    return render_template("index.html", documentos=documentos)

@app.route("/upload", methods=["POST"])
def upload():
    archivos = request.files.getlist("archivo")
    if "usuario" not in session:
        flash("Debes iniciar sesión para subir archivos")
        return redirect(url_for("login"))
    if not archivos or archivos[0].filename == '':
        flash("Sin seleccionar")
        return redirect(url_for("index"))

    for archivo in archivos:
        #Guardar archivo
        ruta = os.path.join(UPLOAD_FOLDER, archivo.filename)
        archivo.save(ruta)

        #Extraer texto según tipo de archivo
        texto = ""
        metadatos = {}

        extension = archivo.filename.rsplit(".", 1)[1].lower()

        if not allowed_file(archivo.filename):
            flash(f"Formato no permitido: {archivo.filename}")
            continue

        #PDF
        if extension == "pdf":
            with pdfplumber.open(ruta) as pdf:
                for pagina in pdf.pages:
                    texto += pagina.extract_text() or ""
                metadatos = pdf.metadata or {}

        #TXT
        elif extension == "txt":
            with open(ruta, "r", encoding="utf-8") as f:
                texto = f.read()

        #DOCX
        elif extension == "docx":
            doc = Document(ruta)
            for p in doc.paragraphs:
                texto += p.text + "\n"

        #JPEG/JPG
        elif extension in ["jpg", "jpeg"]:
            # Aquí normalmente no hay texto, pero podrías usar OCR con pytesseract si quieres
            texto = f"[Archivo de imagen: {archivo.filename}]"

        #Excel XLS/XLSX
        elif extension in ["xls", "xlsx"]:
            import pandas as pd
            df = pd.read_excel(ruta)
            texto = df.to_string()  # convierte toda la hoja a texto

        
        titulo = metadatos.get('/Title', archivo.filename)
        autor = session.get("usuario", "Desconocido")
        fecha_creacion_raw = metadatos.get('/CreationDate', '')
        fecha_creacion = parse_pdf_date(fecha_creacion_raw)
        keywords_str = ", ".join(extract_keywords(texto))

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documentos (nombre_archivo, fecha_subida, contenido, keywords, titulo, autor, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (archivo.filename, datetime.now().strftime("%Y-%m-%d"), texto, keywords_str, titulo, autor, fecha_creacion))
        conn.commit()
        conn.close()

    flash(f"Se han subido {len(archivos)} archivos correctamente.")
    return redirect(url_for("index"))


@app.route("/buscar", methods=["POST"])
def buscar():
    palabra = request.form["palabra"]
    filtro = request.form.get("filtro", "todos")
    termino = "%" + palabra + "%"  # para la búsqueda con LIKE

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if filtro == "usuario":
        # Verificar que el usuario haya iniciado sesión
        if "usuario" not in session:
            flash("Debes iniciar sesión para buscar tus documentos.")
            return redirect(url_for("login"))
        usuario_actual = session["usuario"]

        # Consulta restringida al autor actual
        cursor.execute("""
            SELECT id, nombre_archivo, fecha_subida, titulo, autor, keywords
            FROM documentos
            WHERE autor = ?
              AND (nombre_archivo LIKE ?
                   OR titulo LIKE ?
                   OR keywords LIKE ?
                   OR fecha_subida LIKE ?
                   OR fecha_creacion LIKE ?)
        """, (usuario_actual, termino, termino, termino, termino, termino))

    else:  # "todos" - búsqueda global
        cursor.execute("""
            SELECT id, nombre_archivo, fecha_subida, titulo, autor, keywords
            FROM documentos
            WHERE nombre_archivo LIKE ?
               OR titulo LIKE ?
               OR autor LIKE ?
               OR keywords LIKE ?
               OR fecha_subida LIKE ?
               OR fecha_creacion LIKE ?
        """, (termino, termino, termino, termino, termino, termino))

    resultados = cursor.fetchall()
    conn.close()
    return render_template("resultados.html", resultados=resultados, palabra=palabra)

@app.route("/eliminar_multiple", methods=["POST"])
def eliminar_multiple():
    ids_a_eliminar = request.form.getlist("ids_a_eliminar")
    if not ids_a_eliminar:
        flash("No has seleccionado nada.")
        return redirect(url_for("index"))
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    for id in ids_a_eliminar:
        cursor.execute("SELECT nombre_archivo FROM documentos WHERE id = ?", (id,))
        res = cursor.fetchone()
        if res:
            ruta = os.path.join(UPLOAD_FOLDER, res[0])
            if os.path.exists(ruta): os.remove(ruta)
            cursor.execute("DELETE FROM documentos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Archivos eliminados.")
    return redirect(url_for("index"))

@app.route("/archivo/<nombre>")
def ver_archivo(nombre):
    return send_from_directory(UPLOAD_FOLDER, nombre)

@app.route("/login", methods=["GET", "POST"])
def login():
    # Si ya está logueado, no puede volver a loguearse
    if "usuario" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM usuarios WHERE username=? AND password=?",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session["usuario"] = username
            return redirect(url_for("index"))
        else:
            flash("Credenciales incorrectas")

    return render_template("login.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO usuarios (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            conn.close()
            flash("Usuario creado correctamente. Ahora puedes iniciar sesión.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.close()
            flash("Ese usuario ya existe")

    return render_template("registro.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)