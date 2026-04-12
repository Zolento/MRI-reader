#!/bin/bash

# MRI Reader - Environment Setup Script
# This script sets up the complete development environment using uv

set -e

echo "========================================="
echo "MRI Reader - Environment Setup"
echo "========================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo "Please install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "Or visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "uv found: $(uv --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "Virtual environment already exists, updating..."
    uv venv --clear
else
    uv venv
fi
echo "Virtual environment ready"
echo ""

# Install dependencies
echo "Installing dependencies..."
uv pip install -e .
echo "Dependencies installed"
echo ""

# Verify installation
echo "Verifying installation..."
if uv run python -c "import PyQt5; import numpy; print('All dependencies installed successfully')"; then
    echo ""
    echo "========================================="
    echo "Environment setup complete!"
    echo "========================================="
    echo ""
    echo "To activate the environment and run the application:"
    echo "  source .venv/bin/activate"
    echo "  python -m src.main"
    echo ""
    echo "Or use uv directly:"
    echo "  uv run python -m src.main"
    echo ""
else
    echo ""
    echo "Installation verification failed."
    echo "Please check the error messages above."
    exit 1
fi
