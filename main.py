import streamlit as st
import sqlite3
import requests
from hashlib import sha256
import random

# ---------- CONFIGURACIÓN ----------
st.set_page_config(page_title="📚 Lectura Dinámica", layout="centered")

# ---------- BASE DE DATOS ----------
def init_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, 
        password TEXT, 
        progreso INTEGER DEFAULT 0,
        nivel TEXT DEFAULT 'medio'
    )''')
    conn.commit()
    conn.close()

def register_user(username, password):
    try:
        conn = sqlite3.connect("data.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                  (username, sha256(password.encode()).hexdigest()))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def authenticate_user(username, password):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", 
              (username, sha256(password.encode()).hexdigest()))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_user_progress(username):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("SELECT progreso, nivel FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return {"progreso": row[0], "nivel": row[1]} if row else {"progreso": 0, "nivel": "medio"}

def update_progress(username, resultado, nivel):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("UPDATE users SET progreso = progreso + ?, nivel = ? WHERE username = ?", 
              (resultado, nivel, username))
    conn.commit()
    conn.close()

# ---------- GENERACIÓN DE TEXTO ----------
def generate_text(tema, nivel):
    prompt = f"Escribe un texto educativo para estudiantes de bachillerato sobre {tema}, nivel {nivel}. Que sea claro, dinámico y de unas 300 palabras."
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}"
    }
    data = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]

# ---------- GENERACIÓN DE PREGUNTAS ----------
def generate_questions(text):
    preguntas = []
    ejemplos = [
        ("¿Cuál es el significado más cercano de la palabra 'innovador' en el texto?", ["Moderno", "Antiguo", "Lento", "Oscuro"], "Moderno"),
        ("¿Qué se puede inferir del comportamiento del personaje principal?", ["Es curioso", "Es deshonesto", "Es impaciente", "Es tímido"], "Es curioso"),
        ("¿Cuál es la idea principal del texto?", ["Explicar un fenómeno", "Contar una anécdota", "Vender un producto", "Imitar un estilo"], "Explicar un fenómeno"),
        ("¿Cuál sería un buen título alternativo para el texto?", ["Explorando lo desconocido", "Manual de instrucciones", "Menú del día", "Viaje sin regreso"], "Explorando lo desconocido"),
        ("¿Qué argumento respalda mejor la conclusión del texto?", ["La evidencia científica", "La opinión popular", "El miedo al cambio", "El silencio social"], "La evidencia científica"),
    ]
    seleccionadas = random.sample(ejemplos, 5)
    for enunciado, opciones, correcta in seleccionadas:
        preguntas.append({
            "pregunta": enunciado,
            "opciones": opciones,
            "respuesta_correcta": correcta
        })
    return preguntas

# ---------- EVALUACIÓN ----------
def evaluate_answers(preguntas, respuestas_usuario):
    resultado = 0
    correctas = {}
    for i, pregunta in enumerate(preguntas):
        correcta = pregunta["respuesta_correcta"]
        user_answer = respuestas_usuario.get(i)
        is_correct = user_answer == correcta
        correctas[i] = is_correct
        if is_correct:
            resultado += 1
    return resultado, correctas

# ---------- AJUSTE DE DIFICULTAD ----------
def adjust_difficulty(score, current_level):
    if score >= 4:
        return {"bajo": "medio", "medio": "alto", "alto": "alto"}[current_level]
    elif score <= 2:
        return {"alto": "medio", "medio": "bajo", "bajo": "bajo"}[current_level]
    return current_level

# ---------- INICIALIZAR BD ----------
init_db()

# ---------- INTERFAZ ----------
st.title("📚 Lectura Dinámica para Bachillerato")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.level = "medio"

# Login o Registro
if not st.session_state.logged_in:
    menu = st.radio("Selecciona una opción", ["Iniciar sesión", "Registrarse"])
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if menu == "Iniciar sesión":
        if st.button("Entrar"):
            if authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.level = get_user_progress(username)["nivel"]
                st.success("Inicio de sesión exitoso")
            else:
                st.error("Credenciales incorrectas")
    else:
        if st.button("Registrarse"):
            if register_user(username, password):
                st.success("Usuario registrado. Ahora inicia sesión.")
            else:
                st.error("El usuario ya existe.")
else:
    st.success(f"Bienvenido, {st.session_state.username}")

    tema = st.selectbox("Elige un área temática", ["Cultura general", "Actualidad", "Ciencia", "Tecnología", "Historia", "Filosofía"])

    if st.button("Generar texto"):
        texto = generate_text(tema, st.session_state.level)
        st.session_state.texto = texto
        st.session_state.preguntas = generate_questions(texto)
        st.session_state.respuestas_usuario = {}

    if "texto" in st.session_state:
        st.markdown("### Texto")
        st.write(st.session_state.texto)

        st.markdown("### Preguntas de comprensión")
        for i, pregunta in enumerate(st.session_state.preguntas):
            respuesta = st.radio(pregunta["pregunta"], pregunta["opciones"], key=f"pregunta_{i}")
            st.session_state.respuestas_usuario[i] = respuesta

        if st.button("Enviar respuestas"):
            resultado, correctas = evaluate_answers(st.session_state.preguntas, st.session_state.respuestas_usuario)
            st.write(f"Puntaje: **{resultado}/5**")
            for i, correcta in correctas.items():
                if correcta:
                    st.success(f"✅ Pregunta {i+1}: Correcta")
                else:
                    st.error(f"❌ Pregunta {i+1}: Incorrecta")
            new_level = adjust_difficulty(resultado, st.session_state.level)
            update_progress(st.session_state.username, resultado, new_level)
            st.session_state.level = new_level
            st.info(f"📈 Tu nuevo nivel es: **{new_level}**")
