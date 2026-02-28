"""
import flask
from flask import request, jsonify
app = flask.Flask(__name__)
app.config["DEBUG"] = True

# crear una web para que puedan poner los datos y mostrarlos en una tabla.
# Lo primero es cargar los archivos
# Clasificarlos para incluirlos en un BD con los atributos relevantes, como el nombre del archivo, la fecha de creación, el tamaño, etc.
    # Extraer palabras clave de los archivos para facilitar la búsqueda.
    # Extraer los atributos relevantes de los archivos y guardarlos en una base de datos.
    # cear un indice por nombre y tipo de archivo para facilitar la búsqueda.


   
# Lee el archivo y lo conierte en un dataframe
import pandas as pd
df = pd.read_csv('data.csv')
# Ahora vamos a crear una ruta para mostrar los datos
@app.route('/data', methods=['GET'])
def get_data():
    return jsonify(df.to_dict(orient='records'))    

if __name__ == "__main__":
    app.run()
"""

from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import pdfplumber
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mi_clave_super_secreta_123"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Crear base de datos si no existe
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT,
            fecha_subida TEXT,
            contenido TEXT
        )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/buscar", methods=["POST"])
def buscar():
    palabra = request.form["palabra"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Buscar en nombre_archivo y contenido
    cursor.execute("""
        SELECT id, nombre_archivo, fecha_subida
        FROM documentos
        WHERE nombre_archivo LIKE ? OR contenido LIKE ?
    """, ('%' + palabra + '%', '%' + palabra + '%'))

    resultados = cursor.fetchall()
    conn.close()

    return render_template("resultados.html", resultados=resultados, palabra=palabra)

# Ruta para subir PDF
@app.route("/upload", methods=["POST"])
def upload():
    archivo = request.files.get("archivo")

    if archivo:
        # Guardar archivo en uploads/
        ruta = os.path.join(UPLOAD_FOLDER, archivo.filename)
        archivo.save(ruta)

        # Extraer texto del PDF
        texto = ""
        with pdfplumber.open(ruta) as pdf:
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ""

        # Guardar en base de datos
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO documentos (nombre_archivo, fecha_subida, contenido)
        VALUES (?, ?, ?)
        """, (archivo.filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), texto))
        conn.commit()
        conn.close()

        # Redirigir a la página principal
        flash("PDF subido y guardado correctamente")
        return redirect(url_for("index"))
    flash("No hay ningun archivo seleccionado")
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    #app.run(debug=True)
    app.run(host="0.0.0.0", port=8000, debug=True)