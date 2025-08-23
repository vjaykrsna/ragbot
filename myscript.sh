#!/bin/bash

# MyScript - Development helper script
# Usage: ./myscript.sh [command]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print usage
print_usage() {
    echo "MyScript - Development helper script"
    echo "Usage: ./myscript.sh [command]"
    echo ""
    echo "Commands:"
    echo "  --envscan     Scan for missing environment variables (auto-generates .env.example)"
    echo "  --test        Run all tests"
    echo "  --testquick   Run quick tests (no coverage)"
    echo "  --lint        Run code linting"
    echo "  --format      Format code with black"
    echo "  --clean       Remove cache and temporary folders (__pycache__, .pytest_cache, .ruff_cache, htmlcov, logs, MagicMock)"
    echo "  --venv        Delete the virtual environment (.venv)"
    echo "  --depend      Install requirements.txt and dev-requirements.txt"
    echo "  --docker      Docker operations: up, down, logs, restart"
    echo "  --check       Run comprehensive checks (lint + test + format + clean)"
    echo "  --help        Show this help message"
}

# Function to scan for missing environment variables
scan_env_vars() {
    echo -e "${BLUE}Scanning for missing environment variables...${NC}"
    
    # First generate the .env.example file
    echo -e "${BLUE}Generating .env.example...${NC}"
    if .venv/bin/python -m src.scripts.generate_env_example; then
        echo -e "${GREEN}✓ .env.example generated successfully${NC}"
    else
        echo -e "${RED}✗ Failed to generate .env.example${NC}"
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}⚠️  .env file not found. Creating a template from .env.example${NC}"
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file from .env.example${NC}"
        echo -e "${YELLOW}Please update the .env file with your actual values${NC}"
        return 0
    fi
    
    # Compare environment variables
    echo -e "${BLUE}Comparing .env.example with .env...${NC}"
    
    # Find missing variables (in .env.example but not in .env)
    missing_vars=$(comm -23 <(grep -v '^[#[:space:]]' .env.example | cut -d= -f1 | sort) <(grep -v '^[#[:space:]]' .env | cut -d= -f1 | sort))
    
    if [ -z "$missing_vars" ]; then
        echo -e "${GREEN}✓ All environment variables are present${NC}"
    else
        echo -e "${RED}✗ Missing environment variables:${NC}"
        echo "$missing_vars"
    fi
}

# Function to run all tests
run_tests() {
    echo -e "${BLUE}Running all tests...${NC}"
    if .venv/bin/python -m pytest -v; then
        echo -e "${GREEN}✓ All tests passed${NC}"
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        exit 1
    fi
}

# Function to run quick tests (no coverage)
run_quick_tests() {
    echo -e "${BLUE}Running quick tests...${NC}"
    if .venv/bin/python -m pytest --tb=short -q; then
        echo -e "${GREEN}✓ All quick tests passed${NC}"
    else
        echo -e "${RED}✗ Some quick tests failed${NC}"
        exit 1
    fi
}

# Function to run code linting
run_linting() {
    echo -e "${BLUE}Running code linting...${NC}"
    if .venv/bin/ruff check .; then
        echo -e "${GREEN}✓ Code linting passed${NC}"
    else
        echo -e "${RED}✗ Code linting failed${NC}"
        exit 1
    fi
}

# Function to format code
format_code() {
    echo -e "${BLUE}Formatting code with black...${NC}"
    if .venv/bin/black .; then
        echo -e "${GREEN}✓ Code formatting completed${NC}"
    else
        echo -e "${RED}✗ Code formatting failed${NC}"
        exit 1
    fi
}

# Function to clean cache and temporary folders
clean_folders() {
    echo -e "${BLUE}Cleaning cache and temporary folders...${NC}"

    # List of folders to remove
    folders_to_clean="__pycache__ .pytest_cache .ruff_cache htmlcov logs MagicMock"

    for folder in $folders_to_clean; do
        if find . -name "$folder" -type d -exec rm -rf {} + 2>/dev/null; then
            echo -e "${GREEN}✓ Removed $folder directories${NC}"
        else
            echo -e "${YELLOW}⚠️  No $folder directories found${NC}"
        fi
    done

    echo -e "${GREEN}✓ Cache and temporary folder cleanup completed${NC}"
}

# Function to delete virtual environment
delete_venv() {
    echo -e "${BLUE}Deleting virtual environment...${NC}"

    if [ -d ".venv" ]; then
        if rm -rf .venv; then
            echo -e "${GREEN}✓ Virtual environment (.venv) deleted successfully${NC}"
        else
            echo -e "${RED}✗ Failed to delete virtual environment${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  No .venv directory found${NC}"
    fi
}

# Function to install dependencies
install_dependencies() {
    echo -e "${BLUE}Installing dependencies...${NC}"

    # Install main requirements
    if [ -f "requirements.txt" ]; then
        echo -e "${BLUE}Installing requirements.txt...${NC}"
        if pip install -r requirements.txt; then
            echo -e "${GREEN}✓ requirements.txt installed successfully${NC}"
        else
            echo -e "${RED}✗ Failed to install requirements.txt${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  requirements.txt not found${NC}"
    fi

    # Install dev requirements
    if [ -f "dev-requirements.txt" ]; then
        echo -e "${BLUE}Installing dev-requirements.txt...${NC}"
        if pip install -r dev-requirements.txt; then
            echo -e "${GREEN}✓ dev-requirements.txt installed successfully${NC}"
        else
            echo -e "${RED}✗ Failed to install dev-requirements.txt${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  dev-requirements.txt not found${NC}"
    fi

    echo -e "${GREEN}✓ Dependency installation completed${NC}"
}

# Function to run Docker operations
docker_operations() {
    if [ -z "$2" ]; then
        echo -e "${RED}✗ Docker operation required. Usage: --docker [up|down|logs|restart]${NC}"
        exit 1
    fi

    case "$2" in
        up)
            echo -e "${BLUE}Starting Docker services...${NC}"
            if docker-compose up -d; then
                echo -e "${GREEN}✓ Docker services started successfully${NC}"
            else
                echo -e "${RED}✗ Failed to start Docker services${NC}"
                exit 1
            fi
            ;;
        down)
            echo -e "${BLUE}Stopping Docker services...${NC}"
            if docker-compose down; then
                echo -e "${GREEN}✓ Docker services stopped successfully${NC}"
            else
                echo -e "${RED}✗ Failed to stop Docker services${NC}"
                exit 1
            fi
            ;;
        logs)
            echo -e "${BLUE}Showing Docker logs...${NC}"
            docker-compose logs -f
            ;;
        restart)
            echo -e "${BLUE}Restarting Docker services...${NC}"
            if docker-compose restart; then
                echo -e "${GREEN}✓ Docker services restarted successfully${NC}"
            else
                echo -e "${RED}✗ Failed to restart Docker services${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}✗ Unknown Docker operation: $2${NC}"
            echo -e "${YELLOW}Available operations: up, down, logs, restart${NC}"
            exit 1
            ;;
    esac
}

# Function to run comprehensive checks
run_checks() {
    echo -e "${BLUE}Running comprehensive checks...${NC}"

    # Run linting
    echo -e "${BLUE}Running linting...${NC}"
    if .venv/bin/ruff check .; then
        echo -e "${GREEN}✓ Linting passed${NC}"
    else
        echo -e "${RED}✗ Linting failed${NC}"
        exit 1
    fi

    # Run tests
    echo -e "${BLUE}Running tests...${NC}"
    if .venv/bin/python -m pytest --tb=short -q; then
        echo -e "${GREEN}✓ Tests passed${NC}"
    else
        echo -e "${RED}✗ Tests failed${NC}"
        exit 1
    fi

    # Run formatting check
    echo -e "${BLUE}Checking code formatting...${NC}"
    if .venv/bin/black --check .; then
        echo -e "${GREEN}✓ Code formatting is correct${NC}"
    else
        echo -e "${RED}✗ Code formatting issues found${NC}"
        exit 1
    fi

    # Clean cache folders
    echo -e "${BLUE}Cleaning cache folders...${NC}"
    folders_to_clean="__pycache__ .pytest_cache .ruff_cache htmlcov logs MagicMock"
    for folder in $folders_to_clean; do
        find . -name "$folder" -type d -exec rm -rf {} + 2>/dev/null
    done
    echo -e "${GREEN}✓ Cache cleanup completed${NC}"

    echo -e "${GREEN}✓ All checks passed successfully${NC}"
}

# Main script logic
case "$1" in
    --envscan)
        scan_env_vars
        ;;
    --test)
        run_tests
        ;;
    --testquick)
        run_quick_tests
        ;;
    --lint)
        run_linting
        ;;
    --format)
        format_code
        ;;
    --clean)
        clean_folders
        ;;
    --venv)
        delete_venv
        ;;
    --depend)
        install_dependencies
        ;;
    --docker)
        docker_operations "$@"
        ;;
    --check)
        run_checks
        ;;
    --help|help|-h)
        print_usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        print_usage
        exit 1
        ;;
esac