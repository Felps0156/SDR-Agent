# SDR Agent (Real Estate Lead Qualification)

This project is an AI-powered Sales Development Representative (SDR) agent designed to qualify real estate leads. It engages in natural conversations to understand user needs, filters leads based on the BANT method (Budget, Authority, Need, Timeline), and schedules appointments via Google Calendar for qualified leads.

## 🚀 Project Overview

- **Core Technology:** Python, LangChain, LangGraph, Google Gemini (`gemini-2.5-flash`).
- **Purpose:** Qualify real estate leads into "Curious" or "Qualified" categories.
- **Key Integrations:**
    - **Google Calendar:** Full management (List, Create, Update, Delete events) for scheduling meetings.
    - **SQLite:** Persists conversation state and history.
- **Safeguards:**
    - **Human-in-the-Loop (HITL):** Requires manual confirmation for sensitive actions like creating or updating calendar events.
    - **PII Middleware:** Redacts emails and URLs from outputs and blocks dangerous code execution patterns in inputs.

## 📂 Project Structure

- **`agent.py`**: The main entry point. Configures the LangChain agent, system prompt, tools, and runs the interactive chat loop.
- **`API/google_auth.py`**: Handles OAuth2 authentication for Google Calendar. Manages `client_secret.json` and `token.json`.
- **`Tools/calendar_tools.py`**: Contains the tool definitions used by the agent:
    - `list_upcoming_events`
    - `create_calendar_event` (Includes HITL confirmation)
    - `search_calendar_events`
    - `update_calendar_event` (Includes HITL confirmation)
    - `delete_calendar_event`
- **`Token/`**: Stores authentication credentials (`client_secret.json` and generated `token.json`).
- **`db.sqlite`**: Local database for storing conversation checkpoints (created automatically).

## 🛠️ Setup & Installation

1.  **Environment Setup:**
    Ensure Python is installed. It is recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Dependencies:**
    Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Credentials:**
    - **Google Gemini:** Ensure your `.env` file contains the necessary API keys (likely `GOOGLE_API_KEY`).
    - **Google Calendar:**
        - Place your Google Cloud OAuth 2.0 client secret JSON file in `Token/client_secret.json`.
        - Upon first run, a browser window will open to authorize access, generating `Token/token.json`.

## ▶️ Running the Agent

To start the interactive agent session:

```bash
python agent.py
```

**Interaction:**
- The agent will run in the terminal.
- Type your messages to interact.
- Type `sair` to exit the application.
- **Note:** When the agent proposes a calendar action (create/update), you will be prompted in the terminal to confirm (`s/N`).

## 🧠 Development Notes

- **System Prompt:** Located in `agent.py`. Defines the "BANT" qualification logic and the distinction between "Curious" and "Qualified" flows.
- **Timezone:** Hardcoded to `America/Sao_Paulo`.
- **Tools:** defined in `Tools/calendar_tools.py` use the `@tool` decorator from LangChain.
- **Safety:** The `PIIMiddleware` in `agent.py` is critical for stripping sensitive data. Do not disable without reason.