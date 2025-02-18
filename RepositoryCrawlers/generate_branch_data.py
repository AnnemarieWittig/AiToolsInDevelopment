import os
import pandas as pd
from dotenv import load_dotenv
from helper.console_access import retrieve_branch_data_new

load_dotenv()

# Setup
REPO_PATH = os.getenv('REPO_PATH')
MAIN_BRANCH = os.getenv('MAIN_BRANCH')
storage_path = os.getenv('STORAGE_PATH') + '/branches.csv'

# Retrieve Branches
branches = retrieve_branch_data_new(REPO_PATH, MAIN_BRANCH)

# Store
df = pd.DataFrame(branches)
df.to_csv(storage_path, index=False)