#!/bin/bash

# MRI Reader - Quick Start Script
# This script runs the MRI Reader application

set -e

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo "Please install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

# Run the application
echo "Starting MRI Reader..."
uv run python -m src.main
