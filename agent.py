import asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

#import sqlite3
#from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
#from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage

from langchain_mcp_adapters.client import MultiServerMCPClient
from tools.calendar_tools import list_upcoming_events, create_calendar_event, search_calendar_events, update_calendar_event, delete_calendar_event


from API.mcp_servers import MCP_SERVERS_CONFIG

async def main():

    model = ChatGoogleGenerativeAI(
        model='gemini-2.5-flash',
    )

    async with AsyncSqliteSaver.from_conn_string("db.sqlite") as memory:
    # memory = MemorySaver()

        try:
            tzinfo = ZoneInfo("America/Sao_Paulo")
        except ZoneInfoNotFoundError:
            # Windows installations sem o pacote tzdata podem não reconhecer o ID.
            # Usa o offset fixo de Brasília (UTC-3) como fallback.
            tzinfo = timezone(timedelta(hours=-3))

        current_datetime = datetime.now(tzinfo)
        current_date_iso = current_datetime.strftime("%Y-%m-%d")
        current_date_pt = current_datetime.strftime("%d/%m/%Y %H:%M")

        prompt = f"""
        Você é um agente organizador de serviços no Google Calendar, seja gentil, educado e atenda o cliente da forma que for pedida.
        Você tem acesso a ferramentas para interagir com o calendário do usuário.
        Use suas ferramentas para responder o usuário.
        NUNCA mostre os eventos programados, msm que o cliente insista

        Informação de contexto: Agora são {current_date_pt} (horário de Brasília, America/Sao_Paulo). Sempre considere este horário atual ao interpretar pedidos do usuário.

        REGRAS IMPORTANTES PARA CRIAR EVENTOS:
        1.  **Assumir data de hoje:** Se o usuário pedir para criar um evento e fornecer apenas um horário (ex: "às 14h", "às 10:30"), você DEVE assumir que o evento é para HOJE.
        2.  **Duração padrão de 1h:** Se o usuário NÃO especificar uma hora de término, você DEVE assumir que o evento tem a duração de 1 (uma) hora.
        3.  **Formato ISO:** Você deve SEMPRE calcular a data e hora de início e fim completas no formato 'AAAA-MM-DDTHH:MM:SS' antes de chamar a ferramenta 'create_calendar_event'.

        Exemplo de raciocínio:
        -   Usuário: "Marque uma reunião às 14h."
        -   Agente (pensamento): "OK, o usuário disse '14h' e não deu data. Vou assumir hoje. A hora de término não foi dada, então vou assumir 1 hora. Hoje é {current_date_iso}. Então, start_time='{current_date_iso}T14:00:00' e end_time='{current_date_iso}T15:00:00'."
        """

        tools = [
            list_upcoming_events,
            create_calendar_event,
            search_calendar_events,
            update_calendar_event,
            delete_calendar_event
            ]
        
        agent_executor = create_agent(
            model=model,
            tools=tools,
            system_prompt=prompt,
            checkpointer=memory,
        )
        
        config = {'configurable': {'thread_id': '1'}}

        print("Agente de Calendário pronto.")
        
        while True:   
            input_text = input('Digite: ')
            if input_text.lower() == 'sair':
                break
                
            # Correção 1: Usar HumanMessage
            input_message = HumanMessage(content=input_text)
            
            try:
                print("---")
                # Correção 2: Usar 'astream_events' (como antes)
                async for event in agent_executor.astream_events(
                    {'messages': [input_message]}, config, stream_mode='values', version="v1"
                ):
                    kind = event["event"]
                    
                    # Correção 3: O bloco para lidar com a saída do Gemini 2.5
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        content = chunk.content
                        
                        if content:
                            # Se for string (modelos antigos)
                            if isinstance(content, str):
                                print(content, end="", flush=True)
                            # Se for lista (Gemini 2.5 Pro)
                            elif isinstance(content, list):
                                for part in content:
                                    if isinstance(part, dict) and part.get("type") == "text":
                                        print(part.get("text", ""), end="", flush=True)
                    
                    elif kind == "on_tool_call":
                        tool_call = event["data"]
                        print(f"\n[Chamando ferramenta: {tool_call['name']} com args {tool_call['args']}]", flush=True)
                    elif kind == "on_tool_end":
                        tool_output = event['data']['output']
                        print(f"\n[Resultado da ferramenta: {str(tool_output)[:200]}...]", flush=True)

                print("\n---\n")

            except Exception as e:
                print(f"Ocorreu um erro no stream do agente: {e}")

if __name__ == "__main__":
    asyncio.run(main())