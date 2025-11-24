import asyncio
import os
import pandas as pd
import edge_tts
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoClip, ImageClip, AudioFileClip, CompositeAudioClip, 
    concatenate_videoclips, CompositeVideoClip
)
import numpy as np
import textwrap

# --- CONFIGURACIÓN GLOBAL ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "preguntas.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "Montserrat-Bold.ttf")

LOGO_PATH = os.path.join(BASE_DIR, "assets", "images", "logo.png") # Asegúrate que este nombre coincida con tu logo

# Rutas de Audio (Debes tener estos archivos)
AUDIO_TEMP = os.path.join(BASE_DIR, "assets", "audio", "temp.mp3")
AUDIO_BG = os.path.join(BASE_DIR, "assets", "audio", "background.mp3")
AUDIO_CLOCK = os.path.join(BASE_DIR, "assets", "audio", "clock.mp3")
AUDIO_SUCCESS = os.path.join(BASE_DIR, "assets", "audio", "success.mp3")

# Crear carpetas si no existen
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(AUDIO_TEMP), exist_ok=True)

# Configuración Visual
W, H = 1080, 1920
COLOR_BG = "#000000"
COLOR_ACCENT = "#FFD700" # Amarillo
COLOR_CORRECT = "#00CC00" # Verde
COLOR_BOX = "#1E1E1E"    # Gris oscuro

async def generate_voice(text, filename):
    """Genera audio con respaldo (Edge -> Google)"""
    try:
        communicate = edge_tts.Communicate(text, "es-MX-DaliaNeural", rate="+10%")
        await communicate.save(filename)
    except Exception:
        try:
            tts = gTTS(text=text, lang='es', tld='com.mx')
            tts.save(filename)
        except Exception as e:
            print(f"❌ Error audio: {e}")

def create_base_image(question, options, correct_option=None):
    """Dibuja la base estática (Fondo, Logo, Pregunta, Cajas)"""
    img = Image.new('RGB', (W, H), color=COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    # 1. Cargar Fuentes
    try:
        font_q = ImageFont.truetype(FONT_PATH, 75)
        font_opt = ImageFont.truetype(FONT_PATH, 55)
    except:
        font_q = ImageFont.load_default()
        font_opt = ImageFont.load_default()

    # 2. Dibujar Logo (Pequeño arriba centro)
    try:
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo = logo.resize((150, 150))
            # Pegar logo centrado arriba
            img.paste(logo, (int((W-150)/2), 100), logo)
    except:
        pass

    # 3. Dibujar Pregunta
    lines = textwrap.wrap(question, width=22)
    y_text = 350 # Bajamos un poco para dejar espacio al logo
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_q)
        text_w = bbox[2] - bbox[0]
        draw.text(((W - text_w) / 2, y_text), line, font=font_q, fill="white")
        y_text += 90

    # 4. Dibujar Opciones
    start_y = 800
    gap = 170
    labels = ["A", "B", "C", "D"]
    
    for i, option_text in enumerate(options):
        box_color = COLOR_BOX
        text_color = "white"
        
        # Resaltar correcta si es fase de revelación
        if correct_option is not None and option_text == correct_option:
            box_color = COLOR_CORRECT
            text_color = "black"
        
        # Caja
        box_coords = [100, start_y + (i * gap), W - 100, start_y + (i * gap) + 130]
        draw.rectangle(box_coords, fill=box_color)
        
        # Texto
        full_text = f"  {labels[i]}.  {option_text}"
        bbox_opt = draw.textbbox((0, 0), full_text, font=font_opt)
        text_y = box_coords[1] + (130 - (bbox_opt[3] - bbox_opt[1])) / 2 - 10
        draw.text((150, text_y), full_text, font=font_opt, fill=text_color)

    return img

def make_timer_frame(t, duration, base_img_array):
    """Función para animar la barra de tiempo frame a frame"""
    # Convertir array de numpy a Imagen PIL para dibujar
    frame = Image.fromarray(base_img_array)
    draw = ImageDraw.Draw(frame)
    
    # Calcular ancho de la barra (de Lleno a Vacío)
    progress = 1 - (t / duration) # Va de 1.0 a 0.0
    bar_width = int(W * progress)
    
    # Dibujar barra abajo
    draw.rectangle([0, H - 40, bar_width, H], fill=COLOR_ACCENT)
    
    return np.array(frame)

async def create_video_for_row(row, index):
    print(f"🎬 Procesando video {index + 1}...")
    
    question = row['pregunta']
    correct = row['correcta']
    # Mezclar opciones
    import random
    opts = [row['incorrecta1'], row['incorrecta2'], row['incorrecta3'], correct]
    random.shuffle(opts)
    
    # --- 1. PREPARAR AUDIO ---
    await generate_voice(question, AUDIO_TEMP)
    voice_clip = AudioFileClip(AUDIO_TEMP)
    
    THINK_TIME = 5.0 # Tiempo para pensar
    REVEAL_TIME = 2.5 # Tiempo mostrando respuesta
    
    # --- 2. GENERAR CLIPS DE VIDEO ---
    
    # A. Clip Pregunta (Estático mientras habla la voz)
    img_base_q = create_base_image(question, opts, correct_option=None)
    clip_q = ImageClip(np.array(img_base_q)).set_duration(voice_clip.duration)
    
    # B. Clip Pensar (Animado: Barra bajando)
    # Usamos VideoClip con una función make_frame para animar
    img_base_think = np.array(create_base_image(question, opts, correct_option=None))
    clip_think = VideoClip(lambda t: make_timer_frame(t, THINK_TIME, img_base_think), duration=THINK_TIME)
    
    # C. Clip Revelar (Estático con respuesta verde)
    img_base_reveal = create_base_image(question, opts, correct_option=correct)
    clip_reveal = ImageClip(np.array(img_base_reveal)).set_duration(REVEAL_TIME)
    
    # Unir video visualmente
    final_video = concatenate_videoclips([clip_q, clip_think, clip_reveal])
    
    # --- 3. MEZCLA DE AUDIO (CAPAS) ---
    audios = []
    
    # Capa 1: Voz (Empieza en 0)
    audios.append(voice_clip.set_start(0))
    
    # Capa 2: Reloj (Empieza cuando termina la voz, dura el tiempo de pensar)
    if os.path.exists(AUDIO_CLOCK):
        clock = AudioFileClip(AUDIO_CLOCK).subclip(0, THINK_TIME)
        audios.append(clock.set_start(voice_clip.duration).volumex(0.8))
        
    # Capa 3: Éxito (Empieza al revelar)
    if os.path.exists(AUDIO_SUCCESS):
        success = AudioFileClip(AUDIO_SUCCESS)
        audios.append(success.set_start(voice_clip.duration + THINK_TIME).volumex(0.7))
        
    # Capa 4: Música de Fondo (Todo el video, volumen bajo)
    if os.path.exists(AUDIO_BG):
        bg_music = AudioFileClip(AUDIO_BG)
        # Si la música es más corta que el video, hacemos loop
        if bg_music.duration < final_video.duration:
            bg_music = bg_music.loop(duration=final_video.duration)
        else:
            bg_music = bg_music.subclip(0, final_video.duration)
        audios.append(bg_music.set_start(0).volumex(0.2)) # Volumen bajo (20%)
        
    # Combinar audios
    final_audio = CompositeAudioClip(audios)
    final_video = final_video.set_audio(final_audio)
    
    # --- 4. RENDER ---
    output_filename = os.path.join(OUTPUT_DIR, f"video_{index+1}.mp4")
    # preset='ultrafast' para pruebas rápidas, 'medium' para calidad final
    final_video.write_videofile(output_filename, fps=24, preset='ultrafast', logger=None)
    print(f"✅ Video {index+1} COMPLETADO.")

async def main():
    df = pd.read_csv(DATA_PATH)
    
    # --- MODO FÁBRICA: Genera todos los videos ---
    # Si quieres probar solo 1, cambia df.iterrows() por [df.iloc[0]]
    print(f"🚀 Iniciando producción masiva...")
    for i, row in df.iterrows():
        try:
            await create_video_for_row(row, i)
        except Exception as e:
            print(f"⚠️ Falló video {i}: {e}")

if __name__ == "__main__":
    asyncio.run(main())