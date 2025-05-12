import streamlit as st
import sqlite3
import requests
import json

# Configuración inicial
st.title("Lector AI - Mejora tu comprensión lectora")

# Conexión a la base de datos SQLite
conn = sqlite3.connect("lectorai.db")
cursor = conn.cursor()

# Crear tablas si no existen
cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        correo TEXT NOT NULL UNIQUE,
        contrasena TEXT NOT NULL,
        puntaje INTEGER DEFAULT 0,
        nivel TEXT DEFAULT 'basico'
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS progreso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        texto_id TEXT NOT NULL,
        calificacion INTEGER NOT NULL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    );
""")

conn.commit()

# Función para obtener texto y preguntas desde la API
def obtener_texto_y_preguntas(nivel):
    api_key = st.secrets["openrouter_key"]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    prompt = f"Genera un texto sobre cultura general, actualidad, ciencia, tecnología, historia o filosofía, acompañado de 5 preguntas de opción múltiple que evalúen vocabulario, inferencia y pensamiento crítico. Nivel: {nivel}"
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json={
            "model": "meta-llama/llama-4-maverick:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        return "Error al obtener el texto y preguntas."

# Función para registrar usuario
def registrar_usuario(nombre, correo, contrasena):
    cursor.execute("""
        INSERT INTO usuarios (nombre, correo, contrasena)
        VALUES (?, ?, ?);
    """, (nombre, correo, contrasena))
    conn.commit()

# Función para autenticar usuario
def autenticar_usuario(correo, contrasena):
    cursor.execute("""
        SELECT * FROM usuarios
        WHERE correo = ? AND contrasena = ?;
    """, (correo, contrasena))
    return cursor.fetchone()

# Función para actualizar progreso
def actualizar_progreso(usuario_id, texto_id, calificacion):
    cursor.execute("""
        INSERT INTO progreso (usuario_id, fecha, texto_id, calificacion)
        VALUES (?, CURRENT_DATE, ?, ?);
    """, (usuario_id, texto_id, calificacion))
    conn.commit()

# Interfaz de usuario
with st.form("login_form"):
    st.subheader("Inicia sesión o regístrate")
    nombre = st.text_input("Nombre")
    correo = st.text_input("Correo electrónico")
    contrasena = st.text_input("Contraseña", type="password")
    if st.form_submit_button("Registro"):
        registrar_usuario(nombre, correo, contrasena)
        st.success("Registro exitoso. Ahora puedes iniciar sesión.")
    elif st.form_submit_button("Login"):
        usuario = autenticar_usuario(correo, contrasena)
        if usuario:
            st.success("Bienvenido, " + usuario[1])
            # Aquí iría la lógica para mostrar el texto y las preguntas
        else:
            st.error("Correo o contraseña incorrectos.")

# Interfaz principal del estudiante
if st.button("Empezar a leer"):
    nivel = "basico"  # Nivel inicial
    texto_completo = obtener_texto_y_preguntas(nivel)
    
    # Procesar el texto y las preguntas
    # Asumimos que el texto_completo viene en formato JSON con "texto" y "preguntas"
    try:
        data = json.loads(texto_completo)
        texto = data["texto"]
        preguntas = data["preguntas"]
        
        st.subheader("Lee el siguiente texto y responde las preguntas:")
        st.markdown(texto)
        
        score = 0
        for i, pregunta in enumerate(preguntas):
            st.subheader(f"Pregunta {i+1}")
            st.write(pregunta["enunciado"])
            
            opciones = pregunta["opciones"]
            respuesta_usuario = st.radio("", opciones, key=f"pregunta_{i}")
            
            if respuesta_usuario == pregunta["respuesta_correcta"]:
                score += 1
                st.success("Respuesta correcta!")
            else:
                st.error(f"Respuesta incorrecta. La respuesta correcta era {pregunta['respuesta_correcta']}")
        
        st.subheader(f"Calificación final: {score}/{len(preguntas)}")
        
        # Actualizar progreso en la base de datos
        actualizar_progreso(usuario[0], data["texto_id"], score)
        
    except json.JSONDecodeError:
        st.error("Error al procesar el texto y las preguntas.")

# Cerrar la conexión a la base de datos
conn.close()
