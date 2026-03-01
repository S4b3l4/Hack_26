# 1. Usamos una imagen de Python ligera
FROM python:3.11-slim

# 2. Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiamos tus archivos actuales al contenedor
# Esto copiará index.html, resultados.html, proyecto_python... y database.db
COPY . /app

RUN pip install --no-cache-dir flask pdfplumber pandas python-docx
# 5. Exponemos el puerto (ajústalo si tu app usa otro, ej: 5000)
EXPOSE 8000

#Ejecutamos programa
CMD ["python", "proyecto_python_hackudc.py"]