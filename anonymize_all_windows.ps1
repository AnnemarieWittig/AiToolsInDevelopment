# Define the input file, Python script, and destination folder
$INPUT_FILE = "file_list.csv"

# Ensure the input file exists
if (-Not (Test-Path $INPUT_FILE)) {
    Write-Host "Error: Input file '$INPUT_FILE' not found."
    exit 1
}

# Setup environment
$VENV_PATH = "$PWD\venv"  # This expands to the absolute path of the virtual environment
. "$VENV_PATH\Scripts\Activate.ps1"

if (-Not $env:VIRTUAL_ENV) {
    Write-Host "Error: Virtual environment is not activated."
    exit 1
}

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
    $target_path = $fields[9]

    # Create a folder based on the repo name inside the destination folder
    $STORAGE_FOLDER = "$storage_path\$repo"
    New-Item -ItemType Directory -Path $STORAGE_FOLDER -Force | Out-Null

    $LOGFILE = "$STORAGE_FOLDER\script_outputs.log"

    # Write values to the .env file inside the repo folder
    @"
DUMMY_VALUE=aDummyBecauseTheFirstLineIsNotRead
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
TARGET_PATH=$target_path
"@ | Out-File -Encoding utf8 -FilePath ".env"

    Write-Host "Anonymizing files from $repo and storing them at $target_path"

    # Run the Python scripts inside the repo folder
    & python "./anonymize_all.py"

}

Write-Host "All executions completed."