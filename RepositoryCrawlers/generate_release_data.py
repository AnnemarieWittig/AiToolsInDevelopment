import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.standard import substract_and_format_time, retrieve_releases

load_dotenv()

REPO_PATH = os.getenv('REPO_PATH')


releases = retrieve_releases(REPO_PATH)
results = []

for release in releases:
    if not release:
        continue
    release_date = datetime.fromisoformat(release['date'])

    # Add information to results
    results.append({
        'tag': release['tag'],
        'sha': release['sha'],
        'author': release['author'],
        'date': release['date'],
        'message': release['message']
    })

df = pd.DataFrame(results)
df.to_csv('releases.csv', index=False)
