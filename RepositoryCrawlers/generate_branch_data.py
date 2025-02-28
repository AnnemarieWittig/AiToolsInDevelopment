import os
import pandas as pd
from dotenv import load_dotenv
from helper.git_console_access import retrieve_branch_data_new
from helper.anonymizer import replace_all_user_occurences
import json
load_dotenv(override=True)

# Setup
REPO_PATH = os.getenv('REPO_PATH')
MAIN_BRANCH = os.getenv('MAIN_BRANCH')
VIRTUAL_ENVIRONMENT_PATH = os.getenv('VIRTUAL_ENVIRONMENT_PATH')
storage_path = os.getenv('STORAGE_PATH') + '/branches.csv'

# Retrieve Branches
branches = retrieve_branch_data_new(REPO_PATH, MAIN_BRANCH, VIRTUAL_ENVIRONMENT_PATH)

# Store
df = pd.DataFrame(branches)
if len(df) > 0:
    df = replace_all_user_occurences(df, REPO_PATH)
    # df = hash_and_replace_substrings(df, 'created_by', 'created_by_username')
    # df.drop(columns=['created_by_username'], inplace=True)
df.to_csv(storage_path, index=False)
