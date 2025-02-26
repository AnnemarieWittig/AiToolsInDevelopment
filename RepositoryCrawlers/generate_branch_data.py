import os
import pandas as pd
from dotenv import load_dotenv
from helper.git_console_access import retrieve_branch_data_new
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
df.to_csv(storage_path, index=False)