import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDS_PATH = "Token/client_secret.json" 
TOKEN_PATH = "Token/token.json"


def get_calendar_service():
   """
   Autentica com a API do Google Calendar e retorna o objeto 'service'.
   Lida com o fluxo OAuth2, criando/atualizando token.json.
   """
   creds = None
   
   if os.path.exists(TOKEN_PATH):
       try:
           creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
       except Exception as e:
           print(f"Erro ao carregar token.json: {e}. Re-autenticando...")
           creds = None
           
   if not creds or not creds.valid:
       if creds and creds.expired and creds.refresh_token:
           try:
               creds.refresh(Request())
           except Exception as e:
               print(f"Erro ao atualizar token: {e}")
               print("Token revogado ou inválido. Por favor, autorize novamente.")
               if os.path.exists(TOKEN_PATH):
                   os.remove(TOKEN_PATH) 
               creds = None
       
       if not creds:
           if not os.path.exists(CREDS_PATH):
               raise FileNotFoundError(
                   f"Arquivo de credenciais não encontrado: {CREDS_PATH}. "
                   "Faça o download do JSON no Google Cloud Console e renomeie-o."
               )
           flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
           creds = flow.run_local_server(port=0)
           
       with open(TOKEN_PATH, "w") as token:
           token.write(creds.to_json())

   try:
       service = build("calendar", "v3", credentials=creds)
       print("Serviço do Google Calendar criado com sucesso!")
       return service
   except HttpError as error:
       print(f"Ocorreu um erro ao construir o serviço: {error}")
       return None
   except Exception as e:
       print(f"Um erro inesperado ocorreu: {e}")
       return None

service = get_calendar_service()