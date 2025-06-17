import os
import glob
import shutil
import pandas as pd
from dotenv import load_dotenv
from RepositoryCrawlers.helper.anonymizer import replace_user_data, get_local_git_users
import json

load_dotenv(override=True)

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
OWNER = os.getenv('OWNER')  
REPO = os.getenv('REPO') 
PROJECT = os.getenv('PROJECT')
REPO_PATH = os.getenv('REPO_PATH')
ENDPOINT = os.getenv('ENDPOINT')
MODE = os.getenv('MODE')
STORAGE_PATH = os.getenv('STORAGE_PATH')
TARGET_DIR = os.getenv('TARGET_PATH')
TARGET_PATH = os.path.join(TARGET_DIR, REPO)
anon_columns = {
    'branches.csv': ['created_by','last_author'],
    'commits.csv': ['author', 'message'],
    'pull_requests.csv':  ['author','merged_by','title','description','requested_reviewers','assignees'],
    'releases.csv': ['author'],
    'workflow_runs.csv': ['author', 'name'], 
}

users_mapping = get_local_git_users(REPO_PATH)

# Store user mapping at mapping.json

mapping_path = 'mapping.json'
os.makedirs(TARGET_PATH, exist_ok=True)
with open(mapping_path, 'w') as f:
    json.dump(users_mapping, f, indent=2)
print(f"Saved user mapping to {mapping_path}")
csv_files = glob.glob(os.path.join(STORAGE_PATH, '*.csv'))

if not csv_files:
    print(f"No CSV files found in {STORAGE_PATH}")
else:
    print(f"Found {len(csv_files)} CSV files in {STORAGE_PATH}")

for csv_file in csv_files:
    filename = os.path.basename(csv_file)
    try:
        df = pd.read_csv(csv_file)
    except pd.errors.EmptyDataError:
        print(f"Skipping empty file: {csv_file}")
        continue
    except pd.errors.ParserError:
        print(f"Skipping file with parsing error: {csv_file}")
        continue
    if filename in anon_columns:
        print(f"Anonymizing {csv_file} ...")
        columns_to_anon = anon_columns[filename]
        # Only anonymize specified columns
        df[columns_to_anon] = replace_user_data(df[columns_to_anon], users_mapping)
    else:
        print(f"{csv_file} is stored without anonymization because no options are given.")
        
    anonymized_path = os.path.join(TARGET_PATH, filename)
    os.makedirs(os.path.dirname(anonymized_path), exist_ok=True)
    df.to_csv(anonymized_path, index=False)
    print(f"Saved anonymized file to {anonymized_path}")

# Copy JSON files from source to goal directory
json_files = glob.glob(os.path.join(STORAGE_PATH, '*.json'))
os.makedirs(TARGET_PATH, exist_ok=True)
for json_file in json_files:
    target_path = os.path.join(TARGET_PATH, os.path.basename(json_file))
    shutil.copy2(json_file, target_path)
    print(f"Copied {json_file} to {target_path}")