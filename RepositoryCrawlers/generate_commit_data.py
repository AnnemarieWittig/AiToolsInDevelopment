from helper.git_console_access import retrieve_all_commits_with_stats_and_logging
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv(override=True)

REPO_PATH = os.getenv('REPO_PATH')
STORAGE_PATH = os.getenv('STORAGE_PATH')
store_path = STORAGE_PATH + "/commits.csv"

# Get all Commits
commit_list = retrieve_all_commits_with_stats_and_logging(REPO_PATH)

df = pd.DataFrame(commit_list)

# Create Storage path if not existent, store as csv
if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)
    
df.to_csv(store_path, index=False)
