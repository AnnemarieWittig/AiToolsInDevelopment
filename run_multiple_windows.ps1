# Define the input file, Python script, and destination folder
$INPUT_FILE = "file_list.csv"

# Ensure the input file exists
if (-Not (Test-Path $INPUT_FILE)) {
    Write-Host "Error: Input file '$INPUT_FILE' not found."
    exit 1
}

# Setup environment
$VENV_PATH = "$PWD\venv"  # This expands to the absolute path of the virtual environment
python -m venv $VENV_PATH
. "$VENV_PATH\Scripts\Activate.ps1"

if (-Not $env:VIRTUAL_ENV) {
    Write-Host "Error: Virtual environment is not activated."
    exit 1
}

pip install -r requirements.txt

# Read the file line by line
Get-Content $INPUT_FILE | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "") { return }

    # Parse the CSV line
    $fields = $line -split ","
    $access_token = $fields[0]
    $repo_path = $fields[1]
    $storage_path = $fields[2]
    $owner = $fields[3]
    $repo = $fields[4]
    $main_branch = $fields[5]
    $endpoint = $fields[6]
    $mode = $fields[7]
    $project = $fields[8]

    # Create a folder based on the repo name inside the destination folder
    $STORAGE_FOLDER = "$storage_path\$repo"
    New-Item -ItemType Directory -Path $STORAGE_FOLDER -Force | Out-Null

    $LOGFILE = "$STORAGE_FOLDER\script_outputs.log"

    # Write values to the .env file inside the repo folder
    @"
ACCESS_TOKEN=$access_token
REPO_PATH=$repo_path
STORAGE_PATH=$STORAGE_FOLDER
OWNER=$owner
REPO=$repo
MAIN_BRANCH=$main_branch
ENDPOINT=$endpoint
MODE=$mode
PROJECT=$project
VIRTUAL_ENVIRONMENT_PATH=$VENV_PATH\Scripts
"@ | Out-File -Encoding utf8 -FilePath ".env"

    Write-Host "Running scripts for $repo" | Tee-Object -FilePath $LOGFILE -Append

    # Run the Python scripts inside the repo folder
    & python "./RepositoryCrawlers/generate_branch_data.py" | Tee-Object -FilePath $LOGFILE -Append
    & python "./RepositoryCrawlers/generate_commit_data.py" | Tee-Object -FilePath $LOGFILE -Append
    & python "./RepositoryCrawlers/generate_build_data.py" | Tee-Object -FilePath $LOGFILE -Append
    & python "./RepositoryCrawlers/generate_file_data.py" | Tee-Object -FilePath $LOGFILE -Append
    # & python "./RepositoryCrawlers/generate_issue_data.py" | Tee-Object -FilePath $LOGFILE -Append # Not used here
    & python "./RepositoryCrawlers/generate_pull_request_data.py" | Tee-Object -FilePath $LOGFILE -Append
    & python "./RepositoryCrawlers/generate_release_data.py" | Tee-Object -FilePath $LOGFILE -Append

}

Write-Host "All executions completed."