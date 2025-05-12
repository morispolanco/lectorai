import streamlit as st
import sqlite3
import json
import requests
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Comprensión Lectora", page_icon="📚", layout="wide")

# Ocultar elementos de Streamlit
hide_st_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# Inicializar base de datos
def init_db():
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    
    # Tabla de usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  nombre TEXT,
                  nivel INTEGER DEFAULT 1,
                  fecha_registro TIMESTAMP)''')
    
    # Tabla de progreso
    c.execute('''CREATE TABLE IF NOT EXISTS progreso
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER,
                  fecha TIMESTAMP,
                  tema TEXT,
                  nivel INTEGER,
                  preguntas_correctas INTEGER,
                  total_preguntas INTEGER,
                  FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    
    # Tabla de sesiones
    c.execute('''CREATE TABLE IF NOT EXISTS sesiones
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER,
                  texto TEXT,
                  preguntas TEXT,  # JSON con preguntas y respuestas
                  fecha TIMESTAMP,
                  FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    
    conn.commit()
    conn.close()

init_db()

# Funciones de base de datos
def crear_usuario(username, password, nombre):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO usuarios (username, password, nombre, fecha_registro) VALUES (?, ?, ?, ?)",
                  (username, password, nombre, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verificar_usuario(username, password):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("SELECT id, nombre, nivel FROM usuarios WHERE username = ? AND password = ?", 
              (username, password))
    result = c.fetchone()
    conn.close()
    return result if result else None

def actualizar_nivel(usuario_id, nuevo_nivel):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("UPDATE usuarios SET nivel = ? WHERE id = ?", (nuevo_nivel, usuario_id))
    conn.commit()
    conn.close()

def registrar_progreso(usuario_id, tema, nivel, correctas, total):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("INSERT INTO progreso (usuario_id, fecha, tema, nivel, preguntas_correctas, total_preguntas) VALUES (?, ?, ?, ?, ?, ?)",
              (usuario_id, datetime.now(), tema, nivel, correctas, total))
    conn.commit()
    conn.close()

def guardar_sesion(usuario_id, texto, preguntas):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("INSERT INTO sesiones (usuario_id, texto, preguntas, fecha) VALUES (?, ?, ?, ?)",
              (usuario_id, texto, json.dumps(preguntas), datetime.now()))
    conn.commit()
    conn.close()

def obtener_historial(usuario_id):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("SELECT fecha, tema, nivel, preguntas_correctas, total_preguntas FROM progreso WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 10", (usuario_id,))
    resultados = c.fetchall()
    conn.close()
    return resultados

def obtener_nivel_usuario(usuario_id):
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("SELECT nivel FROM usuarios WHERE id = ?", (usuario_id,))
    nivel = c.fetchone()[0]
    conn.close()
    return nivel

# Funciones para la API de OpenRouter
def generar_texto_y_preguntas(tema, nivel):
    api_key = st.secrets["OPENROUTER_API_KEY"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Ajustar la complejidad según el nivel
    complejidad = {
        1: "básico",
        2: "intermedio",
        3: "avanzado"
    }.get(nivel, "intermedio")
    
    prompt = f"""Genera un texto de aproximadamente 300 palabras sobre {tema} con un nivel de complejidad {complejidad} adecuado para estudiantes de bachillerato. 
    Después del texto, incluye 5 preguntas de opción múltiple que evalúen:
    1. Vocabulario (identificar el significado de palabras en contexto)
    2. Inferencia (extraer información implícita del texto)
    3. Pensamiento crítico (analizar y evaluar el contenido)
    
    Formatea la respuesta así:
    
    [TEXTO]
    <aquí va el texto>
    
    [PREGUNTAS]
    1. Pregunta 1?
    a) Opción 1
    b) Opción 2
    c) Opción 3
    d) Opción 4
    RESPUESTA: a
    
    2. Pregunta 2?
    a) Opción 1
    b) Opción 2
    c) Opción 3
    d) Opción 4
    RESPUESTA: b
    
    (y así para las 5 preguntas)"""
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        resultado = response.json()['choices'][0]['message']['content']
        
        # Procesar la respuesta
        texto = resultado.split('[TEXTO]')[1].split('[PREGUNTAS]')[0].strip()
        preguntas_raw = resultado.split('[PREGUNTAS]')[1].strip().split('\n\n')
        
        preguntas = []
        for p in preguntas_raw:
            if not p.strip():
                continue
            lines = [line.strip() for line in p.split('\n') if line.strip()]
            pregunta_texto = lines[0].split('?')[0] + '?'
            opciones = [opt for opt in lines[1:5] if opt.startswith(('a)', 'b)', 'c)', 'd)'))]
            respuesta = lines[5].split('RESPUESTA: ')[1].strip().lower()
            preguntas.append({
                'pregunta': pregunta_texto,
                'opciones': opciones,
                'respuesta': respuesta
            })
        
        return texto, preguntas
    except Exception as e:
        st.error(f"Error al generar el texto: {str(e)}")
        return None, None

# Interfaz de usuario
def pagina_inicio():
    st.title("📚 Mejora tu Comprensión Lectora")
    st.markdown("""
    Bienvenido a esta aplicación diseñada para ayudarte a mejorar tus habilidades de lectura y comprensión.
    Selecciona **Iniciar Sesión** si ya tienes una cuenta o **Registrarte** si eres nuevo.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Iniciar Sesión"):
            st.session_state.pagina_actual = "iniciar_sesion"
            st.rerun()
    with col2:
        if st.button("Registrarse"):
            st.session_state.pagina_actual = "registrarse"
            st.rerun()

def pagina_registro():
    st.title("📝 Registro de Nuevo Usuario")
    
    with st.form("registro_form"):
        nombre = st.text_input("Nombre completo")
        username = st.text_input("Nombre de usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Registrarse")
        
        if submit:
            if not nombre or not username or not password:
                st.error("Por favor completa todos los campos")
            else:
                if crear_usuario(username, password, nombre):
                    st.success("Registro exitoso. Ahora puedes iniciar sesión.")
                    st.session_state.pagina_actual = "iniciar_sesion"
                    st.rerun()
                else:
                    st.error("El nombre de usuario ya existe. Por favor elige otro.")

    if st.button("Volver al inicio"):
        st.session_state.pagina_actual = "inicio"
        st.rerun()

def pagina_inicio_sesion():
    st.title("🔑 Iniciar Sesión")
    
    with st.form("login_form"):
        username = st.text_input("Nombre de usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar Sesión")
        
        if submit:
            usuario = verificar_usuario(username, password)
            if usuario:
                st.session_state.usuario = {
                    "id": usuario[0],
                    "nombre": usuario[1],
                    "nivel": usuario[2]
                }
                st.session_state.pagina_actual = "menu_principal"
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

    if st.button("Volver al inicio"):
        st.session_state.pagina_actual = "inicio"
        st.rerun()

def menu_principal():
    st.title(f"👋 ¡Bienvenido, {st.session_state.usuario['nombre']}!")
    st.markdown(f"""
    **Nivel actual:** {st.session_state.usuario['nivel']}
    
    Selecciona una opción para comenzar:
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📖 Nueva Lectura"):
            st.session_state.pagina_actual = "seleccion_tema"
            st.rerun()
        if st.button("📊 Mi Progreso"):
            st.session_state.pagina_actual = "ver_progreso"
            st.rerun()
    with col2:
        if st.button("🔍 Historial"):
            st.session_state.pagina_actual = "ver_historial"
            st.rerun()
        if st.button("🚪 Cerrar Sesión"):
            del st.session_state.usuario
            st.session_state.pagina_actual = "inicio"
            st.rerun()

def seleccion_tema():
    st.title("📖 Selecciona un Tema")
    
    temas = [
        "Cultura General",
        "Actualidad",
        "Ciencia",
        "Tecnología",
        "Historia",
        "Filosofía"
    ]
    
    tema_seleccionado = st.selectbox("Elige un tema para tu lectura:", temas)
    
    if st.button("Generar Lectura"):
        with st.spinner("Generando contenido educativo..."):
            texto, preguntas = generar_texto_y_preguntas(
                tema_seleccionado, 
                st.session_state.usuario["nivel"]
            )
            
            if texto and preguntas:
                st.session_state.lectura_actual = {
                    "texto": texto,
                    "preguntas": preguntas,
                    "tema": tema_seleccionado,
                    "respuestas_usuario": [None] * len(preguntas),
                    "mostrar_resultados": False
                }
                st.session_state.pagina_actual = "lectura"
                st.rerun()
    
    if st.button("Volver al menú principal"):
        st.session_state.pagina_actual = "menu_principal"
        st.rerun()

def pagina_lectura():
    lectura = st.session_state.lectura_actual
    st.title(f"📖 {lectura['tema']}")
    
    # Mostrar el texto
    st.subheader("Texto para leer:")
    st.markdown(f"<div style='background-color:#f8f9fa; padding:20px; border-radius:10px;'>{lectura['texto']}</div>", 
                unsafe_allow_html=True)
    
    st.divider()
    
    # Mostrar preguntas
    st.subheader("Preguntas de comprensión:")
    
    for i, pregunta in enumerate(lectura['preguntas']):
        st.markdown(f"**{i+1}. {pregunta['pregunta']}**")
        
        opciones = {opt[0]: opt[3:] for opt in pregunta['opciones']}
        respuesta = st.radio(
            f"Selecciona una opción para la pregunta {i+1}:",
            options=list(opciones.keys()),
            format_func=lambda x: f"{x}) {opciones[x]}",
            key=f"pregunta_{i}",
            index=None if lectura['respuestas_usuario'][i] is None else list(opciones.keys()).index(lectura['respuestas_usuario'][i])
        )
        
        lectura['respuestas_usuario'][i] = respuesta
        
        # Mostrar retroalimentación si ya se respondió
        if lectura['mostrar_resultados']:
            if respuesta == pregunta['respuesta']:
                st.success("✅ Correcto!")
            else:
                st.error(f"❌ Incorrecto. La respuesta correcta es {pregunta['respuesta'].upper()}")
    
    # Botones de acción
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔙 Volver al menú"):
            st.session_state.pagina_actual = "menu_principal"
            st.rerun()
    
    with col2:
        if all(lectura['respuestas_usuario']):
            if st.button("📝 Ver resultados"):
                lectura['mostrar_resultados'] = True
                
                # Calcular puntaje
                correctas = sum(
                    1 for i, p in enumerate(lectura['preguntas']) 
                    if lectura['respuestas_usuario'][i] == p['respuesta']
                )
                total = len(lectura['preguntas'])
                
                # Registrar progreso
                registrar_progreso(
                    st.session_state.usuario["id"],
                    lectura['tema'],
                    st.session_state.usuario["nivel"],
                    correctas,
                    total
                )
                
                # Guardar sesión
                guardar_sesion(
                    st.session_state.usuario["id"],
                    lectura['texto'],
                    lectura['preguntas']
                )
                
                # Ajustar nivel según desempeño
                porcentaje = (correctas / total) * 100
                nivel_actual = st.session_state.usuario["nivel"]
                
                if porcentaje >= 80 and nivel_actual < 3:
                    nuevo_nivel = nivel_actual + 1
                    actualizar_nivel(st.session_state.usuario["id"], nuevo_nivel)
                    st.session_state.usuario["nivel"] = nuevo_nivel
                    st.success(f"¡Felicidades! Has subido al nivel {nuevo_nivel}")
                elif porcentaje < 50 and nivel_actual > 1:
                    nuevo_nivel = nivel_actual - 1
                    actualizar_nivel(st.session_state.usuario["id"], nuevo_nivel)
                    st.session_state.usuario["nivel"] = nuevo_nivel
                    st.warning(f"El nivel de dificultad se ha ajustado a {nuevo_nivel} para mejor adaptación")
                
                st.rerun()
    
    with col3:
        if st.button("🔄 Nuevo texto"):
            st.session_state.pagina_actual = "seleccion_tema"
            st.rerun()

def pagina_progreso():
    st.title("📊 Tu Progreso")
    
    # Obtener datos de progreso
    historial = obtener_historial(st.session_state.usuario["id"])
    
    if historial:
        st.subheader("Últimas actividades:")
        for actividad in historial:
            fecha, tema, nivel, correctas, total = actividad
            porcentaje = (correctas / total) * 100
            
            st.markdown(f"""
            **{tema}** (Nivel {nivel}) - {fecha.strftime('%d/%m/%Y')}
            - Puntuación: {correctas}/{total} ({porcentaje:.1f}%)
            """)
            
            # Barra de progreso
            st.progress(porcentaje / 100)
    else:
        st.info("Aún no tienes registros de progreso. Completa algunas lecturas para comenzar.")
    
    if st.button("Volver al menú principal"):
        st.session_state.pagina_actual = "menu_principal"
        st.rerun()

def pagina_historial():
    st.title("🔍 Tu Historial de Lecturas")
    
    conn = sqlite3.connect('comprension_lectora.db')
    c = conn.cursor()
    c.execute("""
        SELECT s.fecha, s.texto, p.tema, p.nivel, p.preguntas_correctas, p.total_preguntas 
        FROM sesiones s
        LEFT JOIN progreso p ON s.usuario_id = p.usuario_id AND s.fecha = p.fecha
        WHERE s.usuario_id = ?
        ORDER BY s.fecha DESC
        LIMIT 5
    """, (st.session_state.usuario["id"],))
    
    sesiones = c.fetchall()
    conn.close()
    
    if sesiones:
        for i, sesion in enumerate(sesiones):
            fecha, texto, tema, nivel, correctas, total = sesion
            with st.expander(f"Lectura {i+1}: {tema} (Nivel {nivel}) - {fecha.strftime('%d/%m/%Y')}"):
                st.markdown(f"**Puntuación:** {correctas}/{total} ({(correctas/total)*100:.1f}%)")
                st.markdown("**Texto:**")
                st.markdown(f"> {texto[:300]}...")
    else:
        st.info("Aún no tienes lecturas registradas en tu historial.")
    
    if st.button("Volver al menú principal"):
        st.session_state.pagina_actual = "menu_principal"
        st.rerun()

# Flujo principal de la aplicación
if 'pagina_actual' not in st.session_state:
    st.session_state.pagina_actual = "inicio"

if st.session_state.pagina_actual == "inicio":
    pagina_inicio()
elif st.session_state.pagina_actual == "registrarse":
    pagina_registro()
elif st.session_state.pagina_actual == "iniciar_sesion":
    pagina_inicio_sesion()
elif st.session_state.pagina_actual == "menu_principal":
    menu_principal()
elif st.session_state.pagina_actual == "seleccion_tema":
    seleccion_tema()
elif st.session_state.pagina_actual == "lectura":
    pagina_lectura()
elif st.session_state.pagina_actual == "ver_progreso":
    pagina_progreso()
elif st.session_state.pagina_actual == "ver_historial":
    pagina_historial()
