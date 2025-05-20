from helper.git_console_access import retrieve_all_commits_with_stats_and_logging
from helper.anonymizer import replace_all_user_occurences
import pandas as pd
from dotenv import load_dotenv
import os
import logging

load_dotenv(override=True)

REPO_PATH = os.getenv('REPO_PATH')
STORAGE_PATH = os.getenv('STORAGE_PATH')
REPO = os.getenv('REPO')
store_path = STORAGE_PATH + "/commits.csv"

# Get all Commits
commit_list = retrieve_all_commits_with_stats_and_logging(REPO_PATH)

df = pd.DataFrame(commit_list)

if len(df) > 0:
    # df = replace_all_user_occurences(df,REPO_PATH)
    
    df.to_csv(store_path, index=False)
else:
    logging.warning(f"No Commits found for {REPO}.")
