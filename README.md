# Modular RAG Telegram Bot

[![Python CI](https://github.com/vjaykrsna/ragbot/actions/workflows/ci.yml/badge.svg)](https://github.com/vjaykrsna/ragbot/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A sophisticated RAG-powered Telegram bot that answers questions about your chat history using advanced natural language processing and vector search technologies. Built with a modular architecture for maximum maintainability and scalability.

## ✨ Features

-   **🤖 Telegram Integration**: Seamless bot integration that can be added to groups or used privately
-   **🧠 Advanced RAG Pipeline**: State-of-the-art Retrieval-Augmented Generation using semantic search and LLM-powered responses
-   **💾 Vector Knowledge Base**: ChromaDB-powered vector database for efficient storage and retrieval of knowledge nuggets
-   **🏗️ Modular Architecture**: Clean separation of concerns with dependency injection and testable components
-   **🔄 Streaming Data Pipeline**: Memory-efficient processing of large chat histories with anonymization
-   **📊 Progress Tracking**: Comprehensive progress tracking and resume capabilities for long-running operations
-   **🛡️ Privacy-First**: User anonymization and data protection built into the processing pipeline
-   **🧪 Comprehensive Testing**: 95+ passing tests with CI/CD pipeline for quality assurance
-   **📈 Production Ready**: Rate limiting, error handling, and logging for enterprise deployment

## 🏛️ Project Architecture

The project follows a modular architecture with clear separation of concerns:

### Core Modules (`src/core/`)
-   **`config.py`**: Centralized configuration management using dataclasses with environment variable support
-   **`app.py`**: Application context and dependency injection container
-   **`database.py`**: SQLite database management with connection pooling and transaction support
-   **`logger.py`**: Structured logging using structlog with console and file outputs

### Data Processing Pipeline (`src/processing/`)
-   **`pipeline.py`**: Main orchestrator for the data processing workflow
-   **`data_source.py`**: Database-backed data source with iterator pattern
-   **`external_sorter.py`**: Memory-efficient external sorting for large datasets
-   **`anonymizer.py`**: Privacy-preserving user ID anonymization
-   **`conversation_builder.py`**: Intelligent conversation threading with time-based grouping

### RAG System (`src/rag/`)
-   **`rag_pipeline.py`**: Complete RAG implementation with two-stage retrieval
-   **`litellm_client.py`**: Unified LLM client supporting multiple providers (OpenAI, Gemini, etc.)

### Knowledge Synthesis (`src/synthesis/`)
-   **`knowledge_synthesizer.py`**: Main synthesis orchestrator with parallel processing
-   **`nugget_generator.py`**: LLM-powered knowledge nugget generation from conversations
-   **`nugget_embedder.py`**: Embedding generation with rate limiting and batch processing
-   **`nugget_store.py`**: ChromaDB integration for vector storage and retrieval

### Telegram Integration (`src/`)
-   **`bot/main.py`**: Telegram bot with async message handling and RAG integration
-   **`history_extractor/`**: Comprehensive Telegram data extraction with progress tracking
-   **`scripts/`**: High-level CLI scripts for data processing and bot management

## ⚙️ Configuration

All settings are managed through the `AppSettings` dataclass in `src/core/config.py`. Configuration is loaded from environment variables with support for `.env` files.

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Telegram API Configuration
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE=your_phone_number
PASSWORD=your_2fa_password
BOT_TOKEN=your_bot_token
SESSION_NAME=telegram_session

# Group Configuration
GROUP_IDS=group_id_1,group_id_2

# LLM Configuration (JSON format)
LITELLM_CONFIG_JSON={"model_list": [...], "router_settings": {...}}

# Optional Settings
LOG_LEVEL=INFO
REQUESTS_PER_MINUTE=60
BATCH_SIZE=10
MAX_WORKERS=4
```

### File Structure
```
.
├── src/
│   ├── core/              # Core application services
│   ├── processing/        # Data processing pipeline
│   ├── rag/              # RAG implementation
│   ├── synthesis/        # Knowledge synthesis
│   ├── bot/              # Telegram bot
│   ├── history_extractor/ # Telegram data extraction
│   └── scripts/          # CLI entry points
├── tests/                # Comprehensive test suite
├── docs/                 # Architecture documentation
├── data/                 # Data storage (generated)
├── logs/                 # Application logs (generated)
└── requirements.txt      # Python dependencies
```

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r dev-requirements.txt

# Install pre-commit hooks
pre-commit install
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

### 3. Extract Chat History
```bash
# Extract messages from Telegram groups
python -m src.scripts.extract_history
```

### 4. Build Knowledge Base
```bash
# Process and synthesize knowledge
python -m src.scripts.synthesize_knowledge
```

### 5. Run the Bot
```bash
# Start the Telegram bot
python -m src.bot.main
```

## 🧪 Testing

```bash
# Run the full test suite
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test modules
pytest tests/core/ tests/processing/
```

## 📚 Documentation

-   **`docs/workflow_design.md`**: Complete system architecture and workflow documentation
-   **`docs/knowledge_nugget_schema.md`**: Knowledge nugget data format specification
-   **`docs/knowledge_synthesis_prompt.md`**: LLM prompting strategies and templates
-   **`docs/qa_extraction_prompt.md`**: Question-answer extraction patterns

## 🔧 Development

### Adding New Features
1. Follow the existing modular architecture patterns
2. Add comprehensive tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass before submitting PR

### Code Quality
- Pre-commit hooks for code formatting and linting
- Type hints throughout the codebase
- Comprehensive logging and error handling
- Modular design for testability

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Telethon](https://github.com/LonamiWebs/Telethon)
- Uses [LiteLLM](https://github.com/BerriAI/litellm) for unified LLM access
- Vector storage powered by [ChromaDB](https://github.com/chroma-core/chroma)
- Inspired by modern RAG architectures and privacy-first design principles
