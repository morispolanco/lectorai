
import streamlit as st
import sqlite3
import requests
import json

# Configura la conexión a la base de datos
conn = sqlite3.connect('estudiantes.db')
cursor = conn.cursor()

# Crea la tabla de estudiantes si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS estudiantes (
        id INTEGER PRIMARY KEY,
        nombre TEXT NOT NULL,
        progreso REAL DEFAULT 0
    )
''')

# Crea la tabla de preguntas si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS preguntas (
        id INTEGER PRIMARY KEY,
        estudiante_id INTEGER NOT NULL,
        texto TEXT NOT NULL,
        respuesta_correcta TEXT NOT NULL,
        nivel_dificultad REAL NOT NULL,
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes (id)
    )
''')

# Función para obtener un texto dinámico desde la API de OpenRouter
def obtener_texto():
    api_key = st.secrets.openrouter_api_key
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    data = {
        'model': 'meta-llama/llama-4-maverick:free',
        'messages': [
            {
                'role': 'user',
                'content': 'Genera un texto sobre cultura general'
            }
        ]
    }
    response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return None

# Función para generar preguntas
def generar_preguntas(texto):
    preguntas = []
    for i in range(5):
        pregunta = {
            'texto': f'Pregunta {i+1}: {texto.split(".")[i]}',
            'opciones': [f'Opción {j+1}' for j in range(4)],
            'respuesta_correcta': f'Opción {i+1}'
        }
        preguntas.append(pregunta)
    return preguntas

# Página de registro de estudiantes
def registro_estudiantes():
    st.title('Registro de Estudiantes')
    nombre = st.text_input('Nombre del estudiante')
    if st.button('Registrar'):
        cursor.execute('INSERT INTO estudiantes (nombre) VALUES (?)', (nombre,))
        conn.commit()
        st.success('Estudiante registrado con éxito')

# Página de evaluación
def evaluacion():
    st.title('Evaluación')
    estudiante_id = st.selectbox('Seleccione un estudiante', [row[0] for row in cursor.execute('SELECT id, nombre FROM estudiantes').fetchall()])
    texto = obtener_texto()
    if texto:
        st.write(texto)
        preguntas = generar_preguntas(texto)
        for pregunta in preguntas:
            st.write(pregunta['texto'])
            opcion = st.selectbox('Seleccione una opción', pregunta['opciones'])
            if st.button('Enviar'):
                if opcion == pregunta['respuesta_correcta']:
                    st.success('Respuesta correcta')
                    cursor.execute('INSERT INTO preguntas (estudiante_id, texto, respuesta_correcta, nivel_dificultad) VALUES (?, ?, ?, ?)', 
                                   (estudiante_id, pregunta['texto'], pregunta['respuesta_correcta'], 1))
                else:
                    st.error('Respuesta incorrecta')
                    cursor.execute('INSERT INTO preguntas (estudiante_id, texto, respuesta_correcta, nivel_dificultad) VALUES (?, ?, ?, ?)', 
                                   (estudiante_id, pregunta['texto'], pregunta['respuesta_correcta'], 0))
                conn.commit()

# Página principal
def main():
    st.title('Mejora tu comprensión lectora')
    page = st.selectbox('Seleccione una página', ['Registro de Estudiantes', 'Evaluación'])
    if page == 'Registro de Estudiantes':
        registro_estudiantes()
    elif page == 'Evaluación':
        evaluacion()

if __name__ == '__main__':
    main()
