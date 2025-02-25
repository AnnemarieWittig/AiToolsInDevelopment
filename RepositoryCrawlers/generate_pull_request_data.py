import os, json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.console_access import run_git_command, substract_and_format_time, transform_time, retrieve_pull_requests_parallel
from helper.api_access import retrieve_pull_request_details
import logging

logging.basicConfig(level=logging.ERROR)

load_dotenv(override=True)

# Setup
ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
OWNER = os.getenv('OWNER')  
REPO = os.getenv('REPO') 
REPO_PATH = os.getenv('REPO_PATH')
BOT_USERS = ['dependabot-preview[bot]', 'dependabot[bot]', 'renovate[bot]']
ENDPOINT = os.getenv('ENDPOINT')
storage_path = os.getenv('STORAGE_PATH') + '/pull_requests.json'

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
pull_requests = retrieve_pull_requests_parallel(REPO_PATH, 1)

logging.info(f'found {len(pull_requests)} pull requests')
# Safety Storage
# with open(storage_path, 'w') as file:
#     json.dump(pull_requests, file)
results = []

for pull_request in pull_requests:
    created_at = transform_time(pull_request['created_at'])
    
    # Retrieve additional details from the GitHub API TODO remove here if no api
    pr_details = retrieve_pull_request_details(OWNER, REPO, ACCESS_TOKEN, pull_request['number'], ENDPOINT)
    with open('pull_requests.json', 'w') as file:
        json.dump(pr_details, file)
    
    if not pr_details:
        continue
    elif isinstance(pr_details, list) and len(pr_details) == 1:
        pr_details = pr_details[0]
    
    author = pr_details['user']['login'] if pr_details['user'] else None
    merger = pr_details['merged_by']['login'] if pr_details['merged_by'] else None
    merged_at = pr_details['merged_at'] if pr_details['merged_at'] else None
    state = pr_details['state']
    created_at = pr_details['created_at']
    updated_at = pr_details['updated_at']
    closed_at = pr_details.get('closed_at') 
    title = pr_details.get('title', 'N/A')
    requested_reviewers = [reviewer['login'] for reviewer in pr_details['requested_reviewers']]
    labels = [label['name'] for label in pr_details['labels']]
    assignees = [assignee['login'] for assignee in pr_details['assignees']]

    # Calculate time until first comment // Takes too much time realistically
    # time_till_comment = calculate_till_first_comment(pull_request['number'], created_at, REPO_PATH)

    # Calculate time until closed and merged
    time_until_closed = None
    if closed_at:
        start = transform_time(created_at)
        closed_at = transform_time(closed_at)
        time_until_closed = substract_and_format_time(start, closed_at)
        
    if merged_at:
        start = transform_time(created_at)
        merged_at = transform_time(merged_at)
        time_until_merged = substract_and_format_time(start, merged_at)
        
    pr_selection = {
        'merger': merger,
        'merged_at': merged_at,
        'state': state,
        'created_at': created_at,
        'updated_at': updated_at,
        'closed_at': closed_at,
        'time_until_closed': time_until_closed if closed_at else None,
        'time_until_merged': time_until_merged if merged_at else None,
        'requested_reviewers': requested_reviewers,
        'labels': labels,
        'assignees': assignees,
    }
    
    results.append(
        pull_request | pr_selection
    )

# Store
df = pd.DataFrame(results)
df.to_csv(storage_path.replace('.json', '.csv'), index=False)
