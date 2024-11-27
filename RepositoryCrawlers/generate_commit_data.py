from helper.standard import retrieve_commits, retrieve_commit_stats
import pandas as pd
from datetime import datetime

def get_all_commits(repo_path, parameters={}):
    commits = retrieve_commits(parameters, repo_path)
    detailed_commits = []

    for commit in commits:
        stats = retrieve_commit_stats(commit["sha"], repo_path)
        detailed_commits.append({
            "sha": commit["sha"],
            "author": commit["author"],
            "date": datetime.fromisoformat(commit["date"]),
            "message": commit["message"],
            "loc_added": stats["loc_added"],
            "loc_removed": stats["loc_removed"],
        })

    return detailed_commits

REPO_PATH = "/Users/annemariewittig/TestRepositories/dbpedia-chatbot-backend"  # Change to your local repo path
parameters = {
    "until": "2023-09-10T00:00:00Z",
}

commit_list = get_all_commits(REPO_PATH, parameters)

df = pd.DataFrame(commit_list)
df.to_csv("commits.csv", index=False)
