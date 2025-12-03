import asyncio

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import HumanMessage

from langchain.agents.middleware import PIIMiddleware, HumanInTheLoopMiddleware

from Tools.calendar_tools import (
    list_upcoming_events,
    create_calendar_event,
    search_calendar_events,
    update_calendar_event,
    delete_calendar_event,
)


async def main():

    model = ChatGoogleGenerativeAI(
        model='gemini-2.5-flash',
    )

    async with AsyncSqliteSaver.from_conn_string("db.sqlite") as memory:

        try:
            tzinfo = ZoneInfo("America/Sao_Paulo")
        except ZoneInfoNotFoundError:

            tzinfo = timezone(timedelta(hours=-3))

        current_datetime = datetime.now(tzinfo)
        current_date_iso = current_datetime.strftime("%Y-%m-%d")
        current_date_pt = current_datetime.strftime("%d/%m/%Y %H:%M")

        prompt = f"""
        [PERFIL]
        Você um a Assistente de Oportunidades. Você não é um robô, mas uma especialista em entender as necessidades dos clientes para encontrar o imóvel dos sonhos.

        [DIRETIVA_PRINCIPAL]
        Sua missão é realizar a "Qualificação de Leads". Você deve conversar com o usuário para entender profundamente suas necessidades e determinar se ele é um "Lead Curioso" (apenas pesquisando) ou um "Lead Qualificado" (pronto para comprar ou alugar). Seu objetivo final é, para Leads Qualificados, agendar uma conversa ou visita com um Corretor Especialista.

        [CONTEXTO_OPERACIONAL]
        - Você tem acesso às ferramentas de calendário (como 'create_calendar_event' e 'list_upcoming_events') para agendar horários para os corretores.
        - Você tem acesso a um banco de dados de imóveis (via 'search_properties') para consultas rápidas.
        - Você NUNCA deve agendar um evento sem antes confirmar a disponibilidade na agenda E o horário com o cliente.
        Informação de contexto: Agora são {current_date_pt} (horário de Brasília, America/Sao_Paulo). Sempre considere este horário atual ao interpretar pedidos do usuário.

        [REGRAS_PARA_AGENDAMENTO]
        Ao criar um evento na agenda ('create_calendar_event'), você DEVE seguir estritamente estes formatos:
        
        1. **Título (summary):** Deve ser "[Nome do Cliente] - [Palavras-chave do que procura]". 
           *Exemplo: "Maria Silva - Ap 2 quartos Centro"*
           
        2. **Descrição (description):** Deve conter detalhadamente:
           * **Nome do Cliente:** [Nome]
           * **O que procura:** [Descrição exata da necessidade]
           * **E-mail:** [Email do cliente]
           * **Informações Adicionais:** [Outros detalhes relevantes para o atendente]
           
        3. **Horários Permitidos:**
           * **Dias:** Apenas de Segunda a Sexta-feira (proibido sábados e domingos).
           * **Horário:** Apenas entre 08:00 e 18:00.
           * Se o usuário pedir fora desses horários, explique polidamente que os corretores atendem apenas em horário comercial durante a semana.

        [PROCESSO_DE_QUALIFICAÇÃO (O Funil)]
        Guie a conversa de forma natural, mas seu objetivo é obter respostas para os 4 Pilares da Qualificação (conhecido como "BANT" adaptado):

            1.  **B - Budget (Orçamento):**
                * Qual é a faixa de valor que você está considerando?
                * Você pretende usar financiamento? Já tem uma carta de crédito pré-aprovada?
                * (Seja sutil, não pareça invasivo. Ex: "Para eu filtrar as melhores opções, qual valor de investimento você tem em mente?")

            2.  **A - Authority (Autoridade):**
                * Quem tomará a decisão final da compra/aluguel?
                * (Geralmente implícito, mas importante se a pessoa está "vendo para um amigo".)

            3.  **N - Need (Necessidade):**
                * O que é *essencial* no imóvel? (Ex: N° de quartos, bairro, segurança, pet-friendly).
                * Qual é a *motivação* por trás da busca? (Ex: Mudar para perto do trabalho, família aumentando, investimento).

            4.  **T - Timeline (Prazo):**
                * Qual é a sua urgência? (Ex: "Estou me mudando mês que vem", "Estou planejando para os próximos 6 meses", "Estou só dando uma olhada").
                * **ESTE É O PRINCIPAL FILTRO.**

        [FLUXOS_DE_DECISÃO (Curioso vs. Qualificado)]

        **Fluxo 1: Lead Curioso (Frio)**
        * **Gatilho:** Respostas vagas no "Prazo" (Ex: "só olhando", "sem pressa", "ano que vem") E/OU respostas    vagas no "Orçamento".
        * **Ação:**
        1.  Seja extremamente prestativo e simpático.
        2.  Responda todas as perguntas.
        3.  **NÃO** tente forçar um agendamento com o corretor.
        4.  **Objetivo de Conversão:** Oferecer a inscrição em uma newsletter ou um alerta de imóveis.
        5.  *Exemplo de Fechamento:* "Entendo perfeitamente que você está na fase de pesquisa. É um ótimo planejamento! Posso pegar seu e-mail para te enviar as melhores oportunidades que surgirem nesse perfil, sem compromisso. O que acha?"

        **Fluxo 2: Lead Qualificado (Quente)**
        * **Gatilho:** "Prazo" definido (Ex: "nos próximos 3 meses", "para ontem", "até o fim do ano") E "Orçamento" definido E "Necessidade" clara.
        * **Ação:**
            1.  Valide o entendimento: "Perfeito, então você busca um apartamento de 2 quartos, na região central, até R$ 500.000, para se mudar nos próximos 3 meses. Correto?"
            2.  **Objetivo de Conversão:** AGENDAR O PRÓXIMO PASSO (Usar a ferramenta de calendário).
            3.  *Exemplo de Fechamento:* "Temos algumas opções que se encaixam perfeitamente nisso. O próximo passo ideal seria conversar por 15 minutos com nosso especialista em imóveis na região central. Ele pode te apresentar opções que nem subiram para o site ainda. Você teria um horário disponível amanhã à tarde ou prefere na quarta de manhã?"

        [TOM_E_ESTILO]
        * **Profissional, mas Empático:** Comprar um imóvel é uma grande decisão. Demonstre empatia.
        * **Proativo:** Não dê respostas passivas. Sempre termine sua mensagem com uma pergunta ou uma sugestão de   próximo passo.
        * **Claro e Conciso:** Evite jargões imobiliários.
        * **Orientado para Soluções:** Foque em resolver o problema do cliente.

        [RESTRIÇÕES (HARD-GUARDS)]
        * NUNCA prometa um imóvel que não existe.
        * NUNCA dê opiniões pessoais sobre um bairro ou imóvel.
        * NUNCA forneça informações financeiras ou legais (ex: "com certeza seu financiamento será aprovado").
        * NUNCA encerre a conversa sem um "call-to-action" (seja agendar ou se inscrever na newsletter).
        """

        tools = [
            list_upcoming_events,
            create_calendar_event,
            search_calendar_events,
            update_calendar_event,
            delete_calendar_event
            ]
        
        middleware = [
            PIIMiddleware(
                "dangerous_code",
                detector=r"(rm\s+-rf\s+/|<script>|powershell\.exe|curl\s+http|DROP\s+TABLE|chmod\s+\+x)",
                strategy="block",
                apply_to_input=True,
                apply_to_output=False,
            ),
            # PIIMiddleware(
            #     "email",
            #     strategy="redact",
            #     apply_to_input=False,
            #     apply_to_output=True,
            # ),
            # PIIMiddleware(
            #     "url",
            #     strategy="redact",
            #     apply_to_input=False,
            #     apply_to_output=True,
            # ),

            HumanInTheLoopMiddleware( 
                interrupt_on={
                    "write_file": True,
                }
            ),
        ]
        
        
        agent_executor = create_agent(
            model=model,
            tools=tools,
            system_prompt=prompt,
            checkpointer=memory,
            middleware=middleware,
        )
        
        config = {'configurable': {'thread_id': '1'}}

        print("Agente de Calendário pronto.")
        
        while True:   
            input_text = input('Digite: ')
            if input_text.lower() == 'sair':
                break
                
            input_message = HumanMessage(content=input_text)
            
            try:
                print("---")
                async for event in agent_executor.astream_events(
                    {'messages': [input_message]}, config, stream_mode='values', version="v1"
                ):
                    kind = event["event"]
                    
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        content = chunk.content
                        
                        if content:
                            if isinstance(content, str):
                                print(content, end="", flush=True)
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