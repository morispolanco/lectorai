import os
import json
import requests
import streamlit as st
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Obtener clave desde variables de entorno o secrets
def get_gemini_api_key():
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key
    try:
        return st.secrets["gemini_api_key"]
    except KeyError:
        st.error("No se encontró la clave GEMINI_API_KEY")
        st.stop()

GEMINI_API_KEY = get_gemini_api_key()

def generate_text(topic, difficulty):
    prompt = f"Escribe un texto nivel {difficulty} sobre: {topic}. Incluye vocabulario apropiado para estudiantes de bachillerato."

    https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash :generateContent?key=...

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()

        # Mostrar respuesta completa para depuración
        if "error" in data:
            logging.error(f"Error de Gemini API: {data['error']}")
            return "[ERROR] " + data['error']['message']

        try:
            content = data['candidates'][0]['content']['parts'][0]['text']
            return content
        except (KeyError, IndexError) as e:
            logging.error(f"Estructura inesperada en la respuesta: {data}")
            return "[ERROR] Respuesta inválida del servidor."
    except requests.exceptions.RequestException as e:
        logging.error(f"Error en la solicitud a Gemini API: {e}")
        return f"[ERROR] No se pudo generar el texto. Detalle: {e}"


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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash :generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()

        try:
            content = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logging.error(f"Error al procesar la respuesta: {e}")
            return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Error en la solicitud a Gemini API: {e}")
        return []
