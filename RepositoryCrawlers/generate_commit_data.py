from helper.standard import retrieve_commits, retrieve_commit_stats
import pandas as pd
from datetime import datetime
from helper.api_access import grab_specific_commit
from dotenv import load_dotenv
import os

load_dotenv()

def get_all_commits(repo_path, parameters={}):
    commits = retrieve_commits(parameters, repo_path)
    detailed_commits = []

    for commit in commits:
        stats = retrieve_commit_stats(commit["sha"], repo_path)
        commit_content = grab_specific_commit(OWNER, REPO, ACCESS_TOKEN, commit["sha"])
        parents = [parent["sha"] for parent in commit_content["parents"]]
        detailed_commits.append({
            "sha": commit["sha"],
            "author": commit["author"],
            "date": datetime.fromisoformat(commit["date"]),
            "message": commit["message"],
            "loc_added": stats["loc_added"],
            "loc_deleted": stats["loc_deleted"],
            "parents": parents
        })

    return detailed_commits

REPO_PATH = "/Users/annemariewittig/TestRepositories/dbpedia-chatbot-backend"  # Change to your local repo path
OWNER=os.getenv('OWNER')
REPO=os.getenv('REPO')
ACCESS_TOKEN=os.getenv('GITHUB_ACCESS_TOKEN')
parameters = {
    "until": "2023-08-08T00:00:00Z",
}

commit_list = get_all_commits(REPO_PATH, parameters)

df = pd.DataFrame(commit_list)
df.to_csv("commits.csv", index=False)
