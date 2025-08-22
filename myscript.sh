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