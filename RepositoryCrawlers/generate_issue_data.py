import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.general_purpose import substract_and_format_time, transform_time
from helper.api_access import retrieve_issues_parallel
import logging
load_dotenv(override=True)

logging.basicConfig(level=logging.ERROR)

# Setup
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
OWNER = os.getenv('OWNER') 
REPO = os.getenv('REPO') 
MODE = os.getenv('MODE')
BOT_USERS = ['dependabot-preview[bot]', 'dependabot[bot]', 'renovate[bot]']
STORAGE_PATH = os.getenv('STORAGE_PATH')
ENDPOINT = os.getenv('ENDPOINT')

def format_issue_for_github (issue, time_until_closed):
    return {
        'id': issue['id'],
        'issue_number': issue['number'],
        'title': issue.get('title', 'N/A'),
        'description': issue.get('body', 'N/A'),
        'state': issue['state'],
        'labels': [label['name'] for label in issue['labels']],
        'created_at': issue['created_at'],
        'closed_at': issue['closed_at'],
        'creator': issue['user']['login'] if 'user' in issue else issue.get('author', {}).get('name', 'N/A'),
        'assignees': [assignee['login'] for assignee in issue['assignees']],
        'closer': issue['closed_by']['login'] if issue['closed_by'] else 'N/A',
        'time_until_closed': time_until_closed,
    }

def format_issue_for_gitlab(issue, time_until_closed):
    return {
        'id': issue['id'],
        'issue_number': issue['iid'],  # GitLab uses 'iid' instead of 'number'
        'title': issue.get('title', 'N/A'),
        'description': issue.get('description', 'N/A'),  # GitLab uses 'description' instead of 'body'
        'state': issue['state'],  # 'opened' or 'closed' in GitLab
        'labels': issue.get('labels', []),  # GitLab labels are a simple list of strings
        'created_at': issue['created_at'],
        'closed_at': issue.get('closed_at'),  # GitLab has 'closed_at', but it may be None
        'creator': issue.get('author', {}).get('username', 'N/A'),  # GitLab stores creator in 'author' as 'username'
        'assignees': [assignee['username'] for assignee in issue.get('assignees', [])],  # GitLab uses 'username'
        'closer': issue.get('closed_by', {}).get('username', 'N/A') if issue.get('closed_by') else 'N/A',  # GitLab has 'closed_by'
        'time_until_closed': time_until_closed,
    }


# Retrieve Issues
issues = retrieve_issues_parallel(OWNER, REPO, ACCESS_TOKEN, ENDPOINT, MODE)

results = []
counter = 0

length = len(issues)

# Format Issues
for issue in issues:
    counter += 1
    if counter % 100 == 0:
        logging.info(f"Processed {counter} of {length} issues")
    if not issue or ('user' in issue and issue['user']['login'] in BOT_USERS):
        continue
    
    created_at = transform_time(issue['created_at'][:-1])
    closed_at = None if issue['closed_at'] is None else transform_time(issue['closed_at'][:-1])
    issue_id = issue['id']

    # Calculate time until closed
    time_until_closed = None
    if closed_at:
        time_until_closed = substract_and_format_time(created_at, closed_at)

    if MODE == 'github':
        formatted_issue = format_issue_for_github(issue, time_until_closed=time_until_closed)
    elif MODE == 'gitlab':
        formatted_issue = format_issue_for_gitlab(issue, time_until_closed)
    else:
        logging.error(f"Unsupported MODE for issue retrieval: {MODE}")
        exit(1)
        
    results.append(formatted_issue)

# Store
df = pd.DataFrame(results)
df.to_csv(STORAGE_PATH + '/issues.csv', index=False)