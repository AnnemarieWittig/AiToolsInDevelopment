import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.git_console_access import retrieve_releases
from helper.general_purpose import substract_and_format_time

load_dotenv(override=True)

# Setup
REPO_PATH = os.getenv('REPO_PATH')
storage_path = os.getenv('STORAGE_PATH') + '/releases.csv'

# Retrieve and format Releases
releases = retrieve_releases(REPO_PATH)
results = []

for release in releases:
    if not release:
        continue
    
    # Add information to results
    results.append({
        'tag': release['tag'],
        'sha': release['sha'],
        'author': release['author'],
        'date': release['date'],
        'message': release['message']
    })

# Store
df = pd.DataFrame(results)
df.to_csv(storage_path, index=False)
