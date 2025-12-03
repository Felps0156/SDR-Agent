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
        
        safe_events = []
        for event in events:
            safe_events.append({
                "start": event.get("start", {}).get("dateTime"),
                "end": event.get("end", {}).get("dateTime"),
                "status": event.get("status", "confirmed"),
                "title": event.get("summary", "Compromisso"),
            })

        return safe_events 
        
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
    description: str = None,
    **kwargs
):
    """
    Cria um novo evento no Google Calendar, APENAS SE O HORÁRIO ESTIVER LIVRE.
    - 'start_time' pode ser 'AAAA-MM-DDTHH:MM:SS' ou 'HH:MM:SS' (usa hoje).
    - Se 'end_time' não for fornecido, dura 1h.
    - 'attendees' é lista de e-mails.
    
    REGRAS DE NEGÓCIO:
    - Agendamentos permitidos apenas de Segunda a Sexta, das 08:00 às 18:00.
    - Título (summary) deve ser: "[Nome] - [Assunto/Palavras-chave]"
    - Descrição deve conter: Nome, O que procura, E-mail e detalhes extras.
    """
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."

    local_tz = pytz.timezone("America/Sao_Paulo")
 
    try:

        try:
            start_dt_naive = datetime.fromisoformat(start_time)
        except ValueError:
            time_obj = time.fromisoformat(start_time)
            today = datetime.now(local_tz).date()
            start_dt_naive = datetime.combine(today, time_obj)
    except Exception:
        return (
            "Formato de 'start_time' inválido. "
            "Use 'AAAA-MM-DDTHH:MM:SS' ou 'HH:MM:SS' (para hoje)."
        )

    if start_dt_naive.tzinfo is None:
        start_dt = local_tz.localize(start_dt_naive)
    else:
        start_dt = start_dt_naive.astimezone(local_tz)

    # --- VALIDAÇÃO DE HORÁRIO COMERCIAL E DIAS ÚTEIS ---
    # Dias da semana: 0=Segunda, 1=Terça, ..., 5=Sábado, 6=Domingo
    if start_dt.weekday() >= 5:
        return "Erro: Não é permitido agendar reuniões aos sábados e domingos. Por favor, escolha um dia de segunda a sexta-feira."

    # Horário comercial: 08:00 às 18:00
    # Verifica se o início é antes das 08:00 ou se é a partir das 18:00
    if start_dt.hour < 8 or start_dt.hour >= 18:
        return "Erro: O agendamento deve ser feito apenas em horário comercial (entre 08:00 e 18:00)."
    # ---------------------------------------------------

    if end_time:
        try:
            try:
                end_dt_naive = datetime.fromisoformat(end_time)
            except ValueError:
                time_obj = time.fromisoformat(end_time)
                end_dt_naive = datetime.combine(start_dt.date(), time_obj)
        except Exception:
            return (
                "Formato de 'end_time' inválido. "
                "Use 'AAAA-MM-DDTHH:MM:SS' ou 'HH:MM:SS'."
            )

        if end_dt_naive.tzinfo is None:
            end_dt = local_tz.localize(end_dt_naive)
        else:
            end_dt = end_dt_naive.astimezone(local_tz)
    else:
        end_dt = start_dt + timedelta(hours=1)

    try:
        buffer_minutes = 15
        conflict_check_end_dt = end_dt + timedelta(minutes=buffer_minutes)

        print(
            f"Verificando conflitos ({start_dt.strftime('%H:%M')} "
            f"às {end_dt.strftime('%H:%M')})"
        )

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=conflict_check_end_dt.isoformat(),
                singleEvents=True,
                maxResults=1,
            )
            .execute()
        )

        conflicting_events = events_result.get("items", [])

        if conflicting_events:
            event_summary = conflicting_events[0].get("summary", "desconhecido")
            return (
                "Erro: Horário indisponível. "
                f"Já existe um outro evento ('{event_summary}') "
                "que impede o intervalo automático de 15 minutos após o término."
            )

    except HttpError as error:
        return f"Erro ao verificar conflitos na API: {error}"
    except Exception as e:
        return f"Erro inesperado ao verificar conflitos: {e}"

    print("\n[HITL] Solicitação para CRIAR evento no Google Calendar:")
    print(f"  Título : {summary}")
    print(f"  Início : {start_time}")
    print(f"  Fim    : {end_time}")
    if kwargs:
        print(f"  Extras : {kwargs}")

    resp = input("[HITL] Confirmar criação desse evento? (s/N): ").strip().lower()
    if resp not in ("s", "sim", "y", "yes"):
        print("[HITL] Criação de evento CANCELADA pelo humano.")
        return "Criação de evento cancelada por intervenção humana."
    
    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "America/Sao_Paulo",
        },
        "attendees": [{"email": email} for email in attendees] if attendees else [],
    }

    try:
        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )
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
    attendees: List[str] = None,
    kwargs = None,
):
    """
    Atualiza um evento existente usando seu 'event_id'.
    Forneça apenas os campos que deseja alterar.
    """
    if not service:
        return "Erro: O serviço do Google Calendar não foi inicializado."

    print("\n[HITL] Solicitação para ALTERAR evento no Google Calendar:")
    print(f"  Título : {summary}")
    print(f"  Início : {start_time}")
    print(f"  Fim    : {end_time}")
    if kwargs:
        print(f"  Extras : {kwargs}")

    resp = input("[HITL] Confirmar alteração desse evento? (s/N): ").strip().lower()
    if resp not in ("s", "sim", "y", "yes"):
        print("[HITL] Alteração de evento CANCELADA pelo humano.")
        return "Alteração de evento cancelada por intervenção humana."
    
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