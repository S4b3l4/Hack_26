from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import pdfplumber
import re
from collections import defaultdict
from datetime import datetime
from docx import Document

app = Flask(__name__)
app.secret_key = "mi_clave_super_secreta_123"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

STOPWORDS = {"el","la","los","las","de","y","en","que","a","un","una","con","por","para","del","al","se","es","son","como","más","pero","sus","le","ya","o","este","sí","porque"
             ,"entre","cuando","sin","sobre","también","me","nos","te","lo","le","les","mi","tu","su","nuestro","vuestro","ellos","ellas","yo","tú","él","ella","nosotros","vosotros","ellos","ellas"
             , "ser","estar","haber","tener","hacer","decir","ir","ver","dar","saber","querer","llegar","pasar","deber","poner","parecer","quedar","creer","hablar","llevar","dejar",
             "seguir","encontrar","llamar","venir","pensar","salir","volver","tomar","conocer","vivir","sentir","trabajar","escribir","perder","producir","ocurrir","entender",
             "no", "sí", "había", "lo", "dijo", "así", ""}

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

    if not archivos or archivos[0].filename == '':
        flash("No se ha seleccionado ningún archivo")
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

        
        titulo = metadatos.get('Title', archivo.filename)
        autor = metadatos.get('Author', 'Desconocido')
        fecha_creacion = metadatos.get('CreationDate', '')
        
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
    palabra = "%" + request.form["palabra"] + "%"
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nombre_archivo, fecha_subida, titulo, autor, keywords
        FROM documentos
        WHERE nombre_archivo LIKE ?
           OR titulo LIKE ? 
           OR autor LIKE ? 
           OR keywords LIKE ?
    """, (palabra, palabra, palabra, palabra))
    
    resultados = cursor.fetchall()
    conn.close()
    return render_template("resultados.html", resultados=resultados, palabra=request.form["palabra"])


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

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)