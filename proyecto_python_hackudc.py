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

from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

# Crear base de datos si no existe
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
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

    cursor.execute("SELECT * FROM documentos WHERE contenido LIKE ?", ('%' + palabra + '%',))
    resultados = cursor.fetchall()

    conn.close()

    return render_template("resultados.html", resultados=resultados)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)