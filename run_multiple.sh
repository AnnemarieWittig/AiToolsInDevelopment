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
python3 -m venv "$VENV_PATH"
source ./venv/bin/activate

if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Error: Virtual environment is not activated."
    exit 1
fi

pip install -r requirements.txt

# Read the file line by line
while IFS="," read -r access_token repo_path storage_path owner repo main_branch endpoint mode;
do
    # Trim leading/trailing whitespace
    line="${access_token}${repo_path}${storage_path}${owner}${repo}${main_branch}${endpoint}${mode}"

    # Skip empty or whitespace-only lines
    [[ -z "$line" ]] && continue

    # Create a folder based on the repo name inside the destination folder
    STORAGE_FOLDER="$storage_path/$repo"
    mkdir -p "$STORAGE_FOLDER"

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
VIRTUAL_ENVIRONMENT_PATH=$VENV_PATH/bin
EOF

    echo "Running scripts for $repo"

    # Run the Python script inside the repo folder
    python3 "./RepositoryCrawlers/generate_branch_data.py"
    python3 "./RepositoryCrawlers/generate_commit_data.py"
    python3 "./RepositoryCrawlers/generate_build_data.py"
    python3 "./RepositoryCrawlers/generate_file_data.py"
    # python3 "./RepositoryCrawlers/generate_issue_data.py" #Not used here
    python3 "./RepositoryCrawlers/generate_pull_request_data.py"
    python3 "./RepositoryCrawlers/generate_release_data.py"

done < "$INPUT_FILE"

echo "All executions completed."
