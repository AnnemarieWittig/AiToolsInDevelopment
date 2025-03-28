from helper.git_console_access import retrieve_commit_file_changes, retrieve_file_content
import pandas as pd
import json
import os
import pandas as pd
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

invalid_file_endings = ['.png', '.svg', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico']

load_dotenv(override=True)

REPO_PATH = os.getenv('REPO_PATH')

STORAGE_PATH = os.getenv('STORAGE_PATH')
commits = pd.read_csv(STORAGE_PATH + '/commits.csv')

logging.info("Initializing retrieval of abstract file data.")

files = []
counter = 0
for _, commit in commits.iterrows():
    counter += 1
    
    # Update-Logs
    if counter % 100 == 0:
        logging.info(f"Processed {counter} of {len(commits)} commits for file-level information.")
        
    commit_sha = commit["sha"]
    # Retrieve file changes for the current commit
    file_changes = retrieve_commit_file_changes(commit_sha, REPO_PATH)
    
    commit_files = []
    for change in file_changes:
        file_path = change["file_path"]
        
        # if any(file_path.endswith(ending) for ending in invalid_file_endings):
        #     continue
        
        # Retrieve file content to calculate line count
        file_content = retrieve_file_content(commit_sha, file_path, REPO_PATH)
        if file_content:
            # Count lines by splitting at line breaks
            line_count = file_content.count('\n') + (1 if file_content else 0)
        else:
            line_count = 0

        commit_files.append(change |{
            "line_count": line_count
        })

    files.append({
        "commit_sha": commit_sha,
        "commit_files": commit_files
    })

# Save as JSON, create folder if not exists
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)
with open(STORAGE_PATH + "/files.json", "w") as f:
    json.dump(files, f, indent=4)
