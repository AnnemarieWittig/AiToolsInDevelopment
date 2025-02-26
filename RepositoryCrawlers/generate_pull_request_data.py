import os, json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.git_console_access import run_git_command, retrieve_pull_requests_parallel
from helper.general_purpose import substract_and_format_time, transform_time
from helper.api_access import retrieve_pull_request_details, retrieve_pull_requests_gitlab
import logging

logging.basicConfig(level=logging.ERROR)

load_dotenv(override=True)

# Setup
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
OWNER = os.getenv('OWNER')  
REPO = os.getenv('REPO') 
REPO_PATH = os.getenv('REPO_PATH')
BOT_USERS = ['dependabot-preview[bot]', 'dependabot[bot]', 'renovate[bot]']
ENDPOINT = os.getenv('ENDPOINT')
MODE = os.getenv('MODE')
storage_path = os.getenv('STORAGE_PATH') + '/pull_requests.json'

def get_pr_detail_github(owner, repo, access_token, pr_number, endpoint):
    pr_details = retrieve_pull_request_details(owner, repo, access_token, pr_number, endpoint, MODE)
    if not pr_details:
        return None
    elif isinstance(pr_details, list) and len(pr_details) == 1:
        pr_details = pr_details[0]
    
    return {
        'author': pr_details['user']['login'] if pr_details['user'] else None,
        'merger': pr_details['merged_by']['login'] if pr_details['merged_by'] else None,
        'merged_at': pr_details['merged_at'] if pr_details['merged_at'] else None,
        'state': pr_details['state'],
        'created_at': pr_details['created_at'],
        'updated_at': pr_details['updated_at'],
        'closed_at': pr_details.get('closed_at'),
        'title': pr_details.get('title', 'N/A'),
        'requested_reviewers': [reviewer['login'] for reviewer in pr_details.get('requested_reviewers', [])],
        'labels': [label['name'] for label in pr_details.get('labels', [])],
        'assignees': [assignee['login'] for assignee in pr_details.get('assignees', [])],
    }

def get_pr_detail_gitlab(pull_request):
    return {
        'author': pull_request['author']['username'] if 'username' in pull_request['author'] else pull_request['author'],
        'merger': pull_request['merged_by']['username'] if pull_request.get('merged_by') and 'username' in pull_request['merged_by'] else pull_request.get('merged_by'),
        'merged_at': pull_request.get('merged_at'),
        'state': pull_request['state'],
        'created_at': pull_request['created_at'],
        'updated_at': pull_request['updated_at'],
        'closed_at': pull_request.get('closed_at'),
        'title': pull_request.get('title', 'N/A'),
        'requested_reviewers': [reviewer['username'] if 'username' in reviewer else reviewer for reviewer in pull_request.get('reviewers', [])],
        'labels': pull_request.get('labels', []),
        'assignees': [assignee['username'] if 'username' in assignee else assignee for assignee in pull_request.get('assignees', [])],
    }

def calculate_till_first_comment(pr_number, created_at, repo_path, skip_comments_from_author=True):
    logging.info(f"PR #{pr_number} - Created at: {created_at}")

    # Retrieve comments using git notes
    comments_args = ["notes", "--ref", f"refs/notes/pull/{pr_number}/comments"]
    comments_output = run_git_command(comments_args, repo_path=repo_path)

    first_comment_time = None
    if comments_output:
        for line in comments_output.splitlines():
            user, created_at_str = line.split(",")[:2]
            if skip_comments_from_author and user in BOT_USERS:
                continue

            comment_time = datetime.fromisoformat(created_at_str)
            if first_comment_time is None or (comment_time < first_comment_time and comment_time != created_at):
                first_comment_time = comment_time

    if first_comment_time:
        time_to_first_comment = substract_and_format_time(created_at, first_comment_time)
        return time_to_first_comment
    else:
        return None

# Retrieve Pull Request
if MODE == "gitlab":
    pull_requests = retrieve_pull_requests_gitlab(OWNER, ACCESS_TOKEN, ENDPOINT)
elif MODE == "github":
    pull_requests = retrieve_pull_requests_parallel(REPO_PATH, 1)
else:
    raise ValueError(f"No settings for pr retrieval for mode {MODE}")

logging.info(f'found {len(pull_requests)} pull requests')
# Safety Storage
# with open(storage_path, 'w') as file:
#     json.dump(pull_requests, file)
results = []

for pull_request in pull_requests:
    created_at = transform_time(pull_request['created_at'])
    
    if MODE == 'github':
        pr_details = get_pr_detail_github(OWNER, REPO, ACCESS_TOKEN, pull_request['number'], ENDPOINT)
    elif MODE == 'gitlab':
        pr_details = get_pr_detail_gitlab(pull_request)
    else:
        continue
    
    if not pr_details:
        continue

    # Calculate time until closed and merged
    time_until_closed = None
    if pr_details.get('closed_at'):
        start = transform_time(pr_details['created_at'])
        closed_at = transform_time(pr_details['closed_at'])
        time_until_closed = substract_and_format_time(start, closed_at)
    
    time_until_merged = None
    if pr_details.get('merged_at'):
        start = transform_time(pr_details['created_at'])
        merged_at = transform_time(pr_details['merged_at'])
        time_until_merged = substract_and_format_time(start, merged_at)
    
    pr_details['time_until_closed'] = time_until_closed if pr_details.get('closed_at') else None
    pr_details['time_until_merged'] = time_until_merged if pr_details.get('merged_at') else None
    
    results.append(pull_request | pr_details)

# Store
df = pd.DataFrame(results)
df.to_csv(storage_path.replace('.json', '.csv'), index=False)
