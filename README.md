# Modular RAG Telegram Bot

[![Python CI](https://github.com/your-username/your-repo/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/ci.yml)

This project is a RAG-powered Telegram bot that can answer questions about your chat history. It has been refactored for modularity, maintainability, and scalability, following modern Python best practices.

## Project Architecture

The project is structured to separate concerns, making it easier to test, debug, and extend.

-   **`src/core`**: Contains the core application services, such as settings management (`settings.py`) and centralized initialization (`app.py`).
-   **`src/database.py`**: Encapsulates all database interactions.
-   **`src/processing`**: Houses the modular data processing pipeline. Each step of the pipeline (data source, sorting, anonymization, conversation building) is encapsulated in its own module.
-   **`src/rag`**: Contains the Retrieval-Augmented Generation (RAG) pipeline, which is responsible for querying the knowledge base and generating responses.
-   **`src/bot`**: The main entrypoint for the Telegram bot.
-   **`src/scripts`**: Contains the high-level entrypoint scripts for running the data processing and knowledge synthesis pipelines.
-   **`src/utils`**: A package for utility modules, such as the LiteLLM client and logger.

## Configuration

All application settings are managed through dataclasses in the `src/config` directory. The `AppSettings` class in `src/config/settings.py` is the root settings object. The settings are loaded from a `.env` file and environment variables.

To configure the application, create a `.env` file in the root of the project and add the required environment variables. See `.env.example` for a template.

## Usage

This project uses a virtual environment to manage dependencies. Make sure you have created one and installed the required packages.

### 1. Create and Activate the Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

For production, install the main dependencies:
```bash
pip install -r requirements.txt
```

For development, install the development dependencies as well, which include tools for testing and code quality:
```bash
pip install -r requirements-dev.txt
```

### 3. Install Pre-commit Hooks

This project uses `pre-commit` to run code quality checks before each commit. To install the hooks, run the following command:

```bash
pre-commit install
```

## Testing

This project uses `pytest` for testing. The tests are located in the `tests/` directory and include both high-level pipeline tests and unit tests for specific modules.

To run the full test suite, run the following command from the root of the project:

```bash
pytest
```

### Continuous Integration

This project is equipped with a GitHub Actions CI pipeline that automatically runs all tests and code quality checks on every push and pull request to the `main` branch. This helps ensure that the codebase remains stable and maintainable.

You can see the status of the CI pipeline from the badge at the top of this README.

### 4. Run the Data Extraction Pipeline

This will extract the chat history from Telegram and save it to the SQLite database.

```bash
python -m src.scripts.extract_history
```

### 5. Run the Data Processing Pipeline

This will process the raw data in the database and create the structured conversation data.

```bash
python -m src.scripts.process_data
```

### 6. Run the Knowledge Synthesis Pipeline

This will convert the processed conversations into a searchable knowledge base.

```bash
python -m src.scripts.synthesize_knowledge
```

### 7. Run the Telegram Bot

This will start the Telegram bot, which will use the knowledge base to answer questions.

```bash
python -m src.bot.main
```
