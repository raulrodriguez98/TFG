## ------------------------------------------------------------------------ ##
## ESTRUCTURAS DE DATOS O VARIABLES GLOBALES ##
#  
# Llave para la API del chatbot

shortcut = 'data-har.lnk'
ini_date="2025-06-01 01:00:00"
end_date="2025-06-02 00:59:59"
time_step = 1
users=["11pe"]


# Posibles actividades en cada habitación
actividades_habitaciones = {
    'cocinar' : 'cocina',
    'ducharse' : 'baño',
    'deponer' : 'baño',
    'asearse' : 'baño',
    'pc' : 'habitacion',
    'dormir' : 'dormitorio',
    'descansar' : 'salon',
    'salir' : 'puerta salida',
}

# Acciones por cada actividad
nombre_actividades = {
    'cocinar' : 'cocinar',
    'ducharse' : 'ducharse o bañarse',
    'deponer' : 'ir al baño',
    'asearse' : 'asearse o lavarse la cara',
    'pc' : 'jugar juegos o usar el ordenador',
    'dormir' : 'dormir',
    'descansar' : 'descansar o echarse una siesta',
    'salir' : 'salir de casa',
}

invalid_responses = [
    "silencioso",
    "no se pudo transcribir",
    "no se encontró audio",
    "sin resultados"
]

## ------------------------------------------------------------------------ ##
## LIBRERÍAS E IMPORTS ##

import os
import sys
#import winshell
import google.generativeai as chatbot

import numpy as np
from pandas import read_csv
import pandas as pd
import time

from datetime import datetime, timedelta
import configparser

from google.api_core.exceptions import ResourceExhausted

## Para leer el archivo de configuración en formato UTF-8 y no haya problemas de acentuación
config = configparser.ConfigParser()
with open("contexto_llm.txt", "r", encoding="utf-8") as f:
    config.read_file(f)


# Para comunicación con node.js y recibir comunicación directa de parte del usuario
import requests

import re

## ------------------------------------------------------------------------ ##
## TIEMPO ##

# Zona horaria
off_zone=60*60*2

# Convierte ti en el nº de días transcurridos desde epoch (01/01/1970), ajustado por off_zone
def day_time(ti):
    return int((int)((ti+off_zone)/(60*60*24)))

# Convierte tt en un string en formato "YYYY-MM-DD HH:MM:SS"
def time2str(tt):
    return datetime.fromtimestamp(tt).strftime("%Y-%m-%d %H:%M:%S")

# Convierte end_date (string) as un timestamp
# También imprime la fecha original (end_date), el timestamp (tN), el día absoluto (day_time(tN)) y la fecha legible (time2str(tN))
tN = (int)(datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').timestamp())
print (end_date,"End date is", tN, "day:",day_time(tN), time2str(tN))

# Hace lo mismo que antes pero con ini_date
print(ini_date)
t0 = (int)(datetime.strptime(ini_date, '%Y-%m-%d %H:%M:%S').timestamp())
print (ini_date,"Init date is", t0, "day:",day_time(t0), time2str(t0))

# Crea una lista de timestamps (ts) entre t0 y tN, separados por time_step para obtener intervalos de tiempo uniformes
ts=list(range(t0,tN,time_step))

# Calcula el nº de día relativo a t0 (1 si ti == t0, 2 si se trata del día siguiente)
def day_time0(ti):
    return day_time(ti)-day_time(t0)+1


# Calcula la posición relativa de ti respecto a t0 según los time_step (índice del paso temporal)
def relT(ti):
    return (int)((ti-t0)/time_step)


# Crea una lista de días absolutos entre el día inicial y el final (incluído) y lo imprime
days=list(range(day_time(t0),day_time(tN)+1))
print(days)


# Convierte el nº de día desde 1970 (day_number) en una fecha legible en formato "YYYY-MM-DD"
def getStrDatefrom(day_number):
    reference_date = datetime(1970, 1, 1)
    resulting_date = reference_date + timedelta(days=day_number)
    return resulting_date.strftime("%Y-%m-%d")



## ------------------------------------------------------------------------ ##
## CHATBOT ##

chatbot.configure(api_key='serie-key')
for model in chatbot.list_models():
    print(model.name)
model = chatbot.GenerativeModel(model_name="models/gemini-2.0-flash")



## ------------------------------------------------------------------------ ##
## FUNCIÓN PARA OBTENER TRANSCRIPCIÓN USANDO EL ENDPOINT EXISTENTE EN NODE.JS ##
#
# v1 función comunicación con node.js (siempre espera interacción)
#def obtener_transcripcion():
#    try:
#       response = requests.get("http://localhost:3000/api/transcribe")
#        if response.status_code == 200:
#            data = response.json()
#            return data.get('transcript', 'No se pudo obtener la transcripción')
#        else:
#            print(f"Error al obtener transcripción: {response.status_code} - {response.text}")
#            return None
#    except Exception as e:
#        print(f"Error de conexión con el servidor: {e}")
#        return None
##/

# v2 función comunicación con node.js (se queda con audios que sean válidos)
def obtener_transcripcion():
    try:
        # 1. Primero verificamos si hay interacción reciente
        check_response = requests.get("http://localhost:3000/api/check-interaction")
        
        if check_response.status_code != 200:
            return None
            
        check_data = check_response.json()
        
        # 2. Solo si hay audio reciente, transcribimos
        if check_data.get('status') == 'has_audio':
            response = requests.get("http://localhost:3000/api/transcribe")
            
            if response.status_code == 200:
                data = response.json()
                transcript = data.get('transcript', '').strip()
                
                # Detecta si el usuario dijo algo relevante (no solo ruido)
                if transcript and len(transcript) > 3 and not any (bad in transcript.lower() for bad in invalid_responses):
                    print(f"Usuario dice: {transcript}")
                    return transcript
        else:
            return None  # No hay interacción relevante
    
    except Exception as e:
        print(f"Error al verificar interacción: {e}")
        return None


## ------------------------------------------------------------------------ ##
## FUNCIÓN PARA ENVIAR RESPUESTA DEL CHATBOT USANDO EL ENDPOINT EXISTENTE EN NODE.JS ##
#
def enviar_respuesta_a_server(texto):
    try:
        response = requests.post("http://localhost:3000/api/respuesta-chatbot", json={"texto": texto})
        if response.status_code == 200:
            print("Texto enviado a server.js correctamente.")
        else:
            print(f"Error al enviar la respuesta: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error de conexión con server.js: {e}")


## ------------------------------------------------------------------------ ##
## FUNCIÓN DE ESPERA ACTIVA HASTA QUE EL USUARIO ENVÍE UN MENSAJE ##
def esperar_o_proactivo(timeout, paso=0.5):
    tiempo_inicio = time.time()
    while (time.time() - tiempo_inicio) < timeout:
        resultado = obtener_transcripcion()
        if resultado:
            return resultado
        time.sleep(paso)
    return None



## ------------------------------------------------------------------------ ##
## CARGA DE DATOS

#datos_procesados = winshell.shortcut(shortcut).path
datos_procesados = './datos_prueba'
print(os.listdir(datos_procesados))

# Comprobación de parámetros de configuración
contexto_inicial = config.get('Configuracion', 'contexto_inicial')
print(contexto_inicial)
formato_pregunta = config.get('Configuracion', 'formato_pregunta')
print(formato_pregunta)
formato_preacto = config.get('Configuracion', 'formato_preacto')
print(formato_preacto)

contexto_usuario = config.get("11pe", 'contexto')
contexto = f"{contexto_inicial}{formato_pregunta}{contexto_usuario}"


## ------------------------------------------------------------------------ ##
## INTERACCIÓN IA-USUARIO
wait_time = 30
intentos_max = 6
interacciones_max = 6
n_interacciones = 0
pausa_usuario = 40
historial = []  # Historial para dar consistencia a la conversación

#for ux, user in enumerate(users):
for i in range(interacciones_max):
    #print(user)
    print(f"\n****Interacción nº {n_interacciones+1}****\n")

    transcripcion = esperar_o_proactivo(pausa_usuario, paso=0.5)  # Función para obtener transcripción y dar tiempo al usuario a hablar de nuevo o activar el modo proactivo
    
    print(f"Transcripcion que se enviara al prompt: {transcripcion}")

    # Creación de prompt según si la comprobación de interacción del usuario existe o no
    if transcripcion: # Si el usuario ha interactuado con la IA
        prompt = (
            f"{contexto}\nHistorial de la conversación: "
            + "\n".join(historial)
            + f"\n[Interacción reciente del usuario, DALE PRIORIDAD]: {transcripcion}\nResponde de manera concisa y útil:"
        )
        
        historial.append(f"Usuario: {transcripcion}")   # Añadir lo que dice el usuario al historial
    
    else:             # Si el usuario no ha interactuado con la IA y debe ser proactiva
        # Comportamiento proactivo basado en datos del CSV
        prompt = (
            f"{contexto}\nHistorial de la conversación: "
            + "\n".join(historial)
            + "\n[Modo proactivo]: Sugiere acciones basadas en los datos sin esperar input del usuario."
        )

    intentos = 0
    while intentos < intentos_max:
        try:
            respuesta = model.generate_content(prompt)
            respuesta_texto = respuesta.text.strip()
            print(f"Chatbot responde: {respuesta_texto}")

            # --- Separar texto y puntuación ---
            match = re.match(r'["“]?(.+?)["”]?\s*,\s*(\d+)\)?', respuesta_texto)
            if match:
                solo_texto = match.group(1).strip()
            else:
                solo_texto = respuesta_texto

            historial.append(f"Chatbot: {respuesta_texto}") #Añadir en el historial la repsuesta que dió el chatbot
            enviar_respuesta_a_server(solo_texto)   # Enviar solo el texto al servidor
            #time.sleep(pausa_usuario)   # Dejar tiempo para reacción del usuario
            # Prueba para verificar que funciona TTS con respuesta de chatbot
            #respuesta_prueba = "¡Hola! Esta es una respuesta de prueba para verificar TTS en Node.js."
            #enviar_respuesta_a_server(respuesta_prueba)
            break # Sale si encuentra un resultado exitoso
        except ResourceExhausted as ex:
            print(ex)
            print(f"Recurso agotado. Reintentando en {wait_time} segundos...")
            time.sleep(wait_time)
            intentos += 1
    if intentos == intentos_max:
        print(f"Fallo para obtener una respuesta después de {intentos_max} intentos.")

    n_interacciones += 1

    #Terminación correcta
