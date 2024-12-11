import os, json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.standard import run_git_command, substract_and_format_time, retrieve_pull_requests
from helper.api_access import retrieve_pull_request_details

load_dotenv()

ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
OWNER = os.getenv('OWNER')  # Update with actual owner if needed
REPO = os.getenv('REPO')  # Update with actual repo if needed
REPO_PATH = os.getenv('REPO_PATH')
BOT_USERS = ['dependabot-preview[bot]', 'dependabot[bot]', 'renovate[bot]']

def calculate_till_first_comment(pr_number, created_at, repo_path, skip_comments_from_author=True):
    print(f"PR #{pr_number} - Created at: {created_at}")

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

pull_requests = retrieve_pull_requests(REPO_PATH)
print(json.dumps(pull_requests, indent=4))
results = []

for pull_request in pull_requests:
    created_at = datetime.fromisoformat(pull_request['created_at'])
    
    # Retrieve additional details from the GitHub API TODO remove here if no api
    pr_details = retrieve_pull_request_details(OWNER, REPO, ACCESS_TOKEN, pull_request['number'])
    with open('pull_requests.json', 'w') as file:
        json.dump(pr_details, file)
    
    author = pr_details['user']['login']
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

    # Calculate time until first comment
    # time_till_comment = calculate_till_first_comment(pull_request['number'], created_at, REPO_PATH)

    # Calculate time until closed
    time_until_closed = None
    if closed_at:
        start = datetime.fromisoformat(created_at)
        closed_at = datetime.fromisoformat(closed_at)
        time_until_closed = substract_and_format_time(start, closed_at)
        
    if merged_at:
        start = datetime.fromisoformat(created_at)
        merged_at = datetime.fromisoformat(merged_at)
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

df = pd.DataFrame(results)
df.to_csv('pull_requests.csv', index=False)
