from langchain_core.tools import tool
from googleapiclient.errors import HttpError

from typing import List

import pytz
from datetime import datetime, time, timedelta, timezone


try:
    from API.google_auth import service
except ImportError:
    print("ERRO: Não foi possível encontrar o arquivo 'google_calendar.py'")

try:
    print("Serviço do Google Calendar carregado em calendar_tools.py")
except Exception as e:
    print(f"Erro grave ao inicializar o serviço do Google Calendar: {e}")
    service = None


@tool
def list_upcoming_events(max_results: int = 10):
    """ Recupera listas de calendários da conta do Google Calendar, respeitando o limite definido por max_capacity.

    Parâmetros:
      max_capacity (int, opcional): Número máximo de calendários a serem recuperados. Se fornecido como string, a função a converte para inteiro. O padrão é 200.

    Retorno:
      list: Uma lista de dicionários. Cada dicionário contém os dados formatados do calendário, com as seguintes chaves:
            - 'id': Identificador único do calendário.
            - 'name': Nome ou resumo do calendário.
            - 'description': Descrição do calendário (pode ser vazia).
            - 'primary': Indica se é o calendário principal (True ou False).
            - 'time_zone': Fuso horário associado ao calendário.
            - 'etag': Identificador de versão do calendário.
            - 'access_role': Papel de acesso do usuário ao calendário.

    Funcionamento:
      A função realiza chamadas paginadas à API do Google Calendar. Em cada iteração, são recuperados até 200 itens
      ou o número restante definido por max_capacity. O loop é interrompido quando o número total de itens recuperados
      atinge max_capacity ou quando não há mais páginas de resultados. Após a coleta, os dados de cada calendário são
      "limpos" para conter apenas os campos relevantes e retornados em uma lista."""
    
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."
        
    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        
        if not events:
            return "Nenhum evento encontrado."
        
        return events 
        
    except HttpError as error:
        return f"Erro ao acessar a API do Google Calendar: {error}"
    except Exception as e:
        return f"Erro inesperado ao listar eventos: {e}"

@tool
def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str = None,
    attendees: List[str] = None,
    location: str = None,
    description: str = None
):
    """
    Cria um novo evento no Google Calendar, APENAS SE O HORÁRIO ESTIVER LIVRE.
    - 'start_time' pode ser uma data/hora completa ('AAAA-MM-DDTHH:MM:SS') ou apenas uma hora ('HH:MM:SS').
    - Se apenas a hora for fornecida, o evento será agendado para o dia de HOJE.
    - Se 'end_time' não for fornecido, o evento terá automaticamente a duração de 1 hora.
    - 'attendees' deve ser uma lista de emails (strings).
    - Se o horário já estiver ocupado, a ferramenta retornará uma mensagem de erro e não diga qual evento esta agendado para o msm horario.
    """
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."

    local_tz = pytz.timezone('America/Sao_Paulo') 

    try:
        start_dt_naive = datetime.fromisoformat(start_time)
    except ValueError:
        try:
            time_obj = time.fromisoformat(start_time)
            today = datetime.now(local_tz).date() 
            start_dt_naive = datetime.combine(today, time_obj)
        except ValueError:
            return "Formato de 'start_time' inválido. Use 'AAAA-MM-DDTHH:MM:SS' ou 'HH:MM:SS' (para hoje)."


    if start_dt_naive.tzinfo is None:
        start_dt = local_tz.localize(start_dt_naive)
    else:
        start_dt = start_dt_naive

    if end_time:
        try:
            end_dt_naive = datetime.fromisoformat(end_time)
        except ValueError:
            try:
                time_obj = time.fromisoformat(end_time)
                end_dt_naive = datetime.combine(start_dt.date(), time_obj)
            except ValueError:
                return "Formato de 'end_time' inválido. Use 'AAAA-MM-DDTHH:MM:SS' ou 'HH:MM:SS'."
        
        if end_dt_naive.tzinfo is None:
            end_dt = local_tz.localize(end_dt_naive)
        else:
            end_dt = end_dt_naive
    else:
        end_dt = start_dt + timedelta(hours=1)

    try:
        buffer_minutes = 15
        
        conflict_check_end_dt = end_dt + timedelta(minutes=buffer_minutes)

        print(f"Verificando conflitos para o evento ({start_dt.strftime('%H:%M')} às {end_dt.strftime('%H:%M')})")
        print(f"Aplicando buffer de {buffer_minutes} min. Verificando disponibilidade até {conflict_check_end_dt.strftime('%H:%M')}...")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_dt.isoformat(),
            timeMax=conflict_check_end_dt.isoformat(), 
            singleEvents=True, 
            maxResults=1 
        ).execute()
        
        conflicting_events = events_result.get('items', [])
        
        if conflicting_events:
            event_summary = conflicting_events[0].get('summary', 'desconhecido')
            print(f"Conflito encontrado: {event_summary}")
            
            return f"Erro: Horário indisponível. Embora o evento possa caber, já existe um outro evento ('{event_summary}') que impede o intervalo automático de 15 minutos após o término."

    except HttpError as error:
        return f"Erro ao verificar conflitos na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao verificar conflitos: {e}"
    
    except HttpError as error:
        return f"Erro ao verificar conflitos na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao verificar conflitos: {e}"
    
    print("Nenhum conflito. Criando evento...")
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'attendees': [{'email': email} for email in attendees] if attendees else []
    }

    try:
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Evento criado com sucesso! Link: {created_event.get('htmlLink')}"
    except HttpError as error:
        return f"Erro ao criar evento na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao criar evento: {e}"

@tool
def search_calendar_events(query: str, max_results: int = 10):
    """
    Pesquisa por eventos no Google Calendar que correspondam a uma 'query' (ex: 'Dentista', 'Reunião com Equipe').
    Retorna uma lista de eventos, incluindo o 'id' de cada evento.
    """
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."

    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                q=query, 
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return f"Nenhum evento encontrado com o termo de busca: '{query}'."

        return events
        
    except HttpError as error:
        return f"Erro ao pesquisar eventos na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao pesquisar eventos: {e}"

@tool
def update_calendar_event(
    event_id: str,
    summary: str = None,
    start_time: str = None,
    end_time: str = None,
    location: str = None,
    description: str = None,
    attendees: List[str] = None
):
    """
    Atualiza um evento existente usando seu 'event_id'.
    Forneça apenas os campos que deseja alterar.
    """
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."

    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        if summary is not None:
            event['summary'] = summary
        if location is not None:
            event['location'] = location
        if description is not None:
            event['description'] = description
        if start_time is not None:
            event['start']['dateTime'] = start_time
        if end_time is not None:
            event['end']['dateTime'] = end_time
        if attendees is not None:
            event['attendees'] = [{'email': email} for email in attendees]

        updated_event = (
            service.events()
            .update(calendarId='primary', eventId=event_id, body=event)
            .execute()
        )
        return f"Evento atualizado com sucesso! Link: {updated_event.get('htmlLink')}"
        
    except HttpError as error:
        if error.resp.status == 404:
            return f"Erro: Evento com ID '{event_id}' não encontrado."
        return f"Erro ao atualizar evento na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao atualizar evento: {e}"

@tool
def delete_calendar_event(event_id: str):
    """
    Exclui permanentemente um evento do Google Calendar usando seu 'event_id'.
    Use 'search_calendar_events' ou 'list_upcoming_events' para encontrar o 'event_id' primeiro.
    """
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."

    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"Evento com ID '{event_id}' foi excluído com sucesso."
        
    except HttpError as error:
        if error.resp.status == 404:
            return f"Erro: Evento com ID '{event_id}' não encontrado ou já excluído."
        return f"Erro ao excluir evento na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao excluir evento: {e}"