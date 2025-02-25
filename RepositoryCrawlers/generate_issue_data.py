import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.console_access import substract_and_format_time
from helper.api_access import retrieve_issues_parallel
import logging
load_dotenv(override=True)

logging.basicConfig(level=logging.ERROR)

# Setup
ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
OWNER = os.getenv('OWNER') 
REPO = os.getenv('REPO') 
# Adjust to needs of the repository
BOT_USERS = ['dependabot-preview[bot]', 'dependabot[bot]', 'renovate[bot]']
STORAGE_PATH = os.getenv('STORAGE_PATH')
ENDPOINT = os.getenv('ENDPOINT')

# Retrieve Issues
issues = retrieve_issues_parallel(OWNER, REPO, ACCESS_TOKEN, ENDPOINT)

results = []
counter = 0

length = len(issues)

# Format Issues
for issue in issues:
    counter += 1
    if counter % 100 == 0:
        print(f"Processed {counter} of {length} issues")
    if not issue or issue['user']['login'] in BOT_USERS:
        continue
    created_at = datetime.fromisoformat(issue['created_at'][:-1])
    closed_at = None if issue['closed_at'] is None else datetime.fromisoformat(issue['closed_at'][:-1])
    issue_id = issue['id']

    # Calculate time until closed
    time_until_closed = None
    if closed_at:
        time_until_closed = substract_and_format_time(created_at, closed_at)

    # Add information to results
    results.append({
        'id': issue['id'],
        'issue_number': issue['number'],
        'title': issue.get('title', 'N/A'),
        'description': issue.get('body', 'N/A'),
        'state': issue['state'],
        'labels': [label['name'] for label in issue['labels']],
        'created_at': issue['created_at'],
        'closed_at': issue['closed_at'],
        'creator': issue['user']['login'],
        'assignees': [assignee['login'] for assignee in issue['assignees']],
        'closer': issue['closed_by']['login'] if issue['closed_by'] else 'N/A',
        'time_until_closed': time_until_closed,
    })

# Store
df = pd.DataFrame(results)
df.to_csv(STORAGE_PATH + '/issues.csv', index=False)