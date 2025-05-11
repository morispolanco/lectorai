import os
import requests
import json
import streamlit as st
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Obtener clave desde variables de entorno o secrets
def get_api_key():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key
    try:
        return st.secrets["OPENROUTER_API_KEY"]
    except KeyError:
        st.error("No se encontró la clave API en variables de entorno ni en secrets.toml")
        st.stop()

API_KEY = get_api_key()

def generate_text(topic, difficulty):
    prompt = f"Escribe un texto nivel {difficulty} sobre: {topic}. Incluye vocabulario apropiado para estudiantes de bachillerato."

    payload = {
        "model": "qwen/qwen3-0.6b-04-28:free",
        "messages": [{"role": "user", "content": prompt}]
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions ",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        logging.error(f"Error en la solicitud a la API: {e}")
        return f"[ERROR] No se pudo generar el texto. Detalle: {e}"
    except (KeyError, IndexError) as e:
        logging.error(f"Formato inesperado en la respuesta de la API: {e}")
        return "[ERROR] Respuesta inválida del servidor."

def generate_questions(text):
    if "[ERROR]" in text:
        return []

    prompt = f"""
    Basado en este texto: "{text}"

    Crea 5 preguntas de opción múltiple con 4 opciones cada una.
    - 2 de vocabulario
    - 2 de inferencia
    - 1 de pensamiento crítico

    Formato JSON:
    [
      {{
        "question": "¿Cuál es el significado de X?",
        "options": ["A", "B", "C", "D"],
        "correct": "A"
      }},
      ...
    ]
    """

    payload = {
        "model": "qwen/qwen3-0.6b-04-28:free",
        "messages": [{"role": "user", "content": prompt}]
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions ",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error generando preguntas: {e}")
        return []
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logging.error(f"Error analizando respuesta JSON: {e}")
        return []
