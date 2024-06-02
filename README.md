<!-- @format -->

# Running the Uvicorn Server

This repository includes a script to activate the virtual environment and run the Uvicorn server, compatible with both macOS/Linux and Windows.

## Prerequisites

- Ensure you have Python and `virtualenv` installed.
- Create a virtual environment in the root of your project directory:

  ```bash
  python -m venv env
  ```

- Install the required packages:
  ```bash
  source env/bin/activate  # On macOS/Linux
  .\env\Scripts\activate  # On Windows
  pip install -r requirements.txt
  ```

## Running the Server

### macOS/Linux

1. Ensure the script has executable permissions:
   ```bash
   chmod +x server.sh
   ```
2. Run the script:
   ```bash
   ./run_server.sh
   ```

### Windows

1. Run the script using Git Bash or any compatible shell:
   ```bash
   ./run_server.sh
   ```

The script will:

- Detect your operating system.
- Automatically set executable permissions if needed (macOS/Linux).
- Activate the virtual environment.
- Run the Uvicorn server.
- Deactivate the virtual environment once the server stops.
