#!/bin/bash

# Function to check if virtual environment is activated
is_venv_activated() {
    [ ! -z "$VIRTUAL_ENV" ]
}

# Detect the operating system
if [[ "$OSTYPE" == "linux-gnu"* || "$OSTYPE" == "darwin"* ]]; then
    # macOS or Linux
    echo "Detected macOS/Linux"
    if ! is_venv_activated; then
        source env/bin/activate
         echo "Activate virtual environment"
        # Check if activation was successful
        if ! is_venv_activated; then
            echo "Failed to activate virtual environment"
            exit 1
        fi
    fi
    python server.py
    deactivate
elif [[ "$OSTYPE" == "cygwin" || "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    echo "Detected Windows"
    if ! is_venv_activated; then
        source env/Scripts/activate
        echo "Activate virtual environment"
        # Check if activation was successful
        if ! is_venv_activated; then
            echo "Failed to activate virtual environment"
            exit 1
        fi
    fi
    python server.py
    deactivate
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi
