import os
from datetime import datetime
import requests
import pandas as pd
from dotenv import load_dotenv
from helper.standard import retrieve_via_url, URL_ENDING_TREES, URL_ENDING_BLOBS
import base64

commits = pd.read_csv('commits.csv')

load_dotenv()

ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')

OWNER = 'WSE-research'
REPO = 'AutoML-LLM-Frontend'

parameters = {
    'recursive': '1',
}
files = []
# iterate over commits
for index, commit in commits.iterrows():
    commit_sha = commit['sha']
    ending = URL_ENDING_TREES.format(tree_sha=commit_sha)
    
    tree = retrieve_via_url(OWNER, REPO, ACCESS_TOKEN, ending, parameters)
    
    commit_files = []
    
    for file in tree['tree']:
        if file['type'] != 'blob':
            continue
        
        file_path = file['path']
        file_sha = file['sha']
        file_ending = URL_ENDING_BLOBS.format(blob_sha=file_sha)
        blob_data = retrieve_via_url(OWNER, REPO, ACCESS_TOKEN, file_ending)
        line_count = 0
        
        if 'content' in blob_data and 'encoding' in blob_data and blob_data['encoding'] == 'base64':
            # Decode base64 content
            decoded_content = base64.b64decode(blob_data['content']).decode('utf-8')
            
            # Count lines by splitting at line breaks
            line_count = decoded_content.count('\n') + (1 if decoded_content else 0)
            
        commit_files.append({
            'file_path': file_path,
            'file_sha': file_sha,
            'line_count': line_count
        })
    
    files.append({
        'commit_sha': commit_sha,
        'commit_files': commit_files
    })
    
# files_df = pd.DataFrame(files)
# files_df.to_csv('files.csv', index=False)
    
# Save as json
import json
with open('files.json', 'w') as f:
    json.dump(files, f, indent=4)