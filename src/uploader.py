import os
import shutil # Librería para mover archivos
import pandas as pd
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- CONFIGURACIÓN ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
VIDEO_DIR = os.path.join(BASE_DIR, "output")
# Carpeta cementerio (donde van los videos ya usados)
UPLOADED_DIR = os.path.join(VIDEO_DIR, "subidos") 
CSV_PATH = os.path.join(BASE_DIR, "data", "preguntas.csv")

# Crear carpeta de subidos si no existe
os.makedirs(UPLOADED_DIR, exist_ok=True)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    """Autenticación con Google"""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print("❌ FALTA client_secrets.json")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('youtube', 'v3', credentials=creds)

def upload_video(youtube, file_path, title, description, tags):
    """Sube el video a YouTube"""
    print(f"⬆️ Subiendo: {title}...")
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': "24" 
        },
        'status': {
            'privacyStatus': 'private',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        # if status: print(f"Progreso: {int(status.progress() * 100)}%")
            
    print(f"✅ ÉXITO! ID: {response['id']}")
    return True

def main():
    youtube = get_authenticated_service()
    if not youtube: return

    df = pd.read_csv(CSV_PATH)
    
    # CONFIGURA AQUÍ TU LÍMITE DIARIO
    VIDEOS_UPLOADED_TODAY = 0
    DAILY_LIMIT = 6 

    print("🚀 Iniciando Uploader Inteligente...")
    print(f"📂 Los videos subidos se moverán a: {UPLOADED_DIR}")

    for i, row in df.iterrows():
        if VIDEOS_UPLOADED_TODAY >= DAILY_LIMIT:
            print("🛑 Límite diario alcanzado. Hasta mañana.")
            break

        video_filename = f"video_{i+1}.mp4"
        video_path = os.path.join(VIDEO_DIR, video_filename)

        # SI EL VIDEO NO ESTÁ EN 'OUTPUT', ASUMIMOS QUE YA SE SUBIÓ
        if not os.path.exists(video_path):
            # (Opcional) Imprimir que se salta, o mantener silencio para limpiar consola
            # print(f"⏩ Saltando {video_filename} (No encontrado o ya subido)")
            continue
            
        # Preparar Metadatos
        titulo = f"{row['pregunta']} 🧠 #Trivia #Shorts"[:99]
        desc = (f"Comenta tu respuesta 👇\n\n🧠 Entrena tu cerebro: [TU_LINK]\n\n"
                f"Pregunta: {row['pregunta']}\n#retomental #quiz")
        tags = ["trivia", "quiz", "shorts", "cultura general"]

        try:
            # 1. SUBIR
            if upload_video(youtube, video_path, titulo, desc, tags):
                # 2. MOVER A CARPETA 'SUBIDOS' PARA NO REPETIR
                shutil.move(video_path, os.path.join(UPLOADED_DIR, video_filename))
                print(f"📦 Video movido a carpeta 'subidos'.")
                
                VIDEOS_UPLOADED_TODAY += 1
            
        except Exception as e:
            print(f"❌ Error con {video_filename}: {e}")

if __name__ == "__main__":
    main()