from helper.standard import retrieve_commit_file_changes, retrieve_file_content, run_git_command
import pandas as pd
import json
import os
import pandas as pd
from dotenv import load_dotenv

commits = pd.read_csv('commits.csv')

load_dotenv()

REPO_PATH = os.getenv('REPO_PATH')

files = []
for _, commit in commits.iterrows():
# commit = commits.iloc[1]
# if commit["sha"]:
    commit_sha = commit["sha"]
    
    # git_args = ["ls-tree", "--name-only", "-r", commit_sha]
    # file_list = run_git_command(git_args, repo_path=REPO_PATH)
    # print(f"Files in commit {commit_sha}:\n{file_list}")

    
    # Retrieve file changes for the current commit
    file_changes = retrieve_commit_file_changes(commit_sha, REPO_PATH)
    
    commit_files = []
    for change in file_changes:
        file_path = change["file_path"]
        # loc_added = change["loc_added"]
        # loc_removed = change["loc_removed"]

        # Retrieve file content to calculate line count
        file_content = retrieve_file_content(commit_sha, file_path, REPO_PATH)
        if file_content:
            # Count lines by splitting at line breaks
            line_count = file_content.count('\n') + (1 if file_content else 0)
        else:
            line_count = 0

        commit_files.append(change |{
            # "file_path": file_path,
            # "file_sha": change["file_sha"],
            # "loc_added": loc_added,
            # "loc_removed": loc_removed,
            "line_count": line_count
        })

    files.append({
        "commit_sha": commit_sha,
        "commit_files": commit_files
    })

# Save as JSON
with open("files.json", "w") as f:
    json.dump(files, f, indent=4)
