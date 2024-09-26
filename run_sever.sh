#!/bin/bash

# Activate the virtual environment
source env/bin/activate

# Run the Uvicorn server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
