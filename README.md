# Modular RAG Telegram Bot

[![Python CI](https://github.com/your-username/your-repo/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/ci.yml)

This project is a RAG-powered Telegram bot that can answer questions about your chat history. It has been refactored for modularity, maintainability, and scalability, following modern Python best practices.

## Features

-   **Telegram Integration:** The bot integrates with Telegram and can be added to groups to answer questions.
-   **RAG Pipeline:** The bot uses a Retrieval-Augmented Generation (RAG) pipeline to answer questions. It retrieves relevant information from a knowledge base and then uses a large language model (LLM) to generate a response.
-   **Knowledge Base:** The bot builds a knowledge base from your Telegram chat history. The knowledge base is stored in a ChromaDB vector database.
-   **Modular Architecture:** The project is built with a modular architecture that separates concerns and makes the code easy to test, debug, and extend.
-   **Data Processing Pipeline:** The project includes a data processing pipeline that extracts, processes, and anonymizes your chat history before it's added to the knowledge base.
-   **Pre-commit Hooks:** The project uses pre-commit hooks to run code quality checks before each commit.
-   **CI/CD Pipeline:** The project is equipped with a GitHub Actions CI/CD pipeline that automatically runs all tests and code quality checks on every push and pull request.

## Project Architecture

The project is structured to separate concerns, making it easier to test, debug, and extend.

-   **`src/core`**: Contains the core application services, such as settings management (`config.py`) and centralized initialization (`app.py`).
-   **`src/database`**: Encapsulates all database interactions.
-   **`src/history_extractor`**: Contains the components for extracting chat history from Telegram.
-   **`src/processing`**: Houses the modular data processing pipeline. Each step of the pipeline (data source, sorting, anonymization, conversation building) is encapsulated in its own module.
-   **`src/rag`**: Contains the Retrieval-Augmented Generation (RAG) pipeline, which is responsible for querying the knowledge base and generating responses.
-   **`src/synthesis`**: Contains the components for synthesizing knowledge from processed conversations.
-   **`src/bot`**: The main entrypoint for the Telegram bot.
-   **`src/scripts`**: Contains the high-level entrypoint scripts for running the data processing and knowledge synthesis pipelines.

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

### 4. Set up your environment

Create a `.env` file in the root of the project. You can use the `.env.example` file as a template. You will need to provide your Telegram API credentials and the IDs of the groups you want to scrape.

### 5. Run the Data Extraction Pipeline

This will extract the chat history from the Telegram groups you specified in your `.env` file and save it to the database.

```bash
python -m src.scripts.extract_history
```

### 6. Run the Knowledge Synthesis Pipeline

This will process the raw data in the database, create structured conversations, and then convert them into a searchable knowledge base.

```bash
python -m src.scripts.synthesize_knowledge
```

### 7. Run the Telegram Bot

This will start the Telegram bot, which will use the knowledge base to answer questions.

```bash
python -m src.bot.main
```

## Managing Dependencies

This project uses `pip-tools` to manage dependencies. This helps keep the project's dependencies predictable and easy to update.

**Key Idea:** You only edit the `requirements.in` and `dev-requirements.in` files. The `requirements.txt` and `dev-requirements.txt` files are auto-generated.

### To Add a New Package

1.  Add the package name to `requirements.in` (for main dependencies) or `dev-requirements.in` (for development tools).
2.  Run the following command to update the `.txt` files:
    ```bash
    .venv/bin/pip-compile
    ```
3.  Install the new dependencies:
    ```bash
    .venv/bin/pip-sync
    ```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

### To Upgrade All Packages

1.  Run the following command to find the latest compatible versions:
    ```bash
    .venv/bin/pip-compile --upgrade
    ```
2.  Sync your environment with the new versions:
    ```bash
    .venv/bin/pip-sync
    ```
