# Modular RAG Telegram Bot

This project is a RAG-powered Telegram bot that can answer questions about your chat history. It has been refactored for modularity, maintainability, and scalability, following modern Python best practices.

## Project Architecture

The project is structured to separate concerns, making it easier to test, debug, and extend.

-   **`src/core`**: Contains the core application services, such as settings management (`settings.py`) and centralized initialization (`app.py`).
-   **`src/processing`**: Houses the modular data processing pipeline. Each step of the pipeline (data source, sorting, anonymization, conversation building) is encapsulated in its own module.
-   **`src/rag`**: Contains the Retrieval-Augmented Generation (RAG) pipeline, which is responsible for querying the knowledge base and generating responses.
-   **`src/bot`**: The main entrypoint for the Telegram bot.
-   **`src/scripts`**: Contains the high-level entrypoint scripts for running the data processing and knowledge synthesis pipelines.
-   **`src/utils`**: A package for utility modules, such as the LiteLLM client and logger.

## Configuration

All application settings are managed through the `AppSettings` class in `src/core/settings.py`. This class uses `pydantic-settings` to load configuration from a `.env` file and environment variables.

To configure the application, create a `.env` file in the root of the project and add the required environment variables. See `.env.example` for a template.

## Usage

This project uses a virtual environment to manage dependencies. Make sure you have created one and installed the required packages.

### 1. Create and Activate the Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Data Processing Pipeline

This will process the raw data in the `data/raw` directory and create the structured conversation data in `data/processed`.

```bash
python -m src.scripts.process_data
```

### 4. Run the Knowledge Synthesis Pipeline

This will convert the processed conversations into a searchable knowledge base.

```bash
python -m src.scripts.synthesize_knowledge
```

### 5. Run the Telegram Bot

This will start the Telegram bot, which will use the knowledge base to answer questions.

```bash
python -m src.bot.main
```
