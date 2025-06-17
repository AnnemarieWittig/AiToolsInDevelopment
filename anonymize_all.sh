#!/bin/bash

# Define the input file, Python script, and destination folder
INPUT_FILE="file_list.csv"

# Ensure the input file exists
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: Input file '$INPUT_FILE' not found."
    exit 1
fi

# Setup environment
VENV_PATH="$(pwd)/venv"  # This expands to /absolute/path/to/venv
source "$(pwd)/venv/bin/activate"

if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Error: Virtual environment is not activated."
    exit 1
fi

# Read the file line by line
while IFS="," read -r access_token repo_path storage_path owner repo main_branch endpoint mode project target_path;
do
    # Trim leading/trailing whitespace
    line="${access_token}${repo_path}${storage_path}${owner}${repo}${main_branch}${endpoint}${mode}${project}${target_path}"

    # Skip empty or whitespace-only lines
    [[ -z "$line" ]] && continue

    # Create a folder based on the repo name inside the destination folder
    STORAGE_FOLDER="$storage_path/$repo"
    mkdir -p "$STORAGE_FOLDER"

    LOGFILE="$STORAGE_FOLDER/script_outputs.log"
    # Write values to the .env file inside the repo folder
    cat > ".env" <<EOF
ACCESS_TOKEN=$access_token
REPO_PATH=$repo_path
STORAGE_PATH=$STORAGE_FOLDER
OWNER=$owner
REPO=$repo
MAIN_BRANCH=$main_branch
ENDPOINT=$endpoint
MODE=$mode
PROJECT=$project
VIRTUAL_ENVIRONMENT_PATH=$VENV_PATH/bin
TARGET_PATH=$target_path
EOF

    echo "Anonymizing files from $repo and storing them at $target_path" 2>&1 | tee -a "$LOGFILE"

    python3 "./anonymize_all.py" 

done < "$INPUT_FILE"

echo "All executions completed."
