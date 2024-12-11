import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.api_access import retrieve_workflow_runs
from helper.standard import retrieve_branches
import json
load_dotenv()


REPO_PATH = os.getenv('REPO_PATH')

branches = retrieve_branches(REPO_PATH)

df = pd.DataFrame(branches)
df.to_csv('branches.csv', index=False)