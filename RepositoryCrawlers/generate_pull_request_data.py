import os, json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.git_console_access import run_git_command, retrieve_pull_requests_parallel, retrieve_pr_metadata_via_ls_remote
from helper.general_purpose import transform_time, substract_and_format_time, get_user_name_azure
from helper.api_access import retrieve_pull_request_details, retrieve_pull_requests_gitlab, retrieve_pull_requests_azure
from helper.anonymizer import replace_all_user_occurences
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv(override=True)

# Setup
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
OWNER = os.getenv('OWNER')  
REPO = os.getenv('REPO') 
PROJECT = os.getenv('PROJECT')
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
        'merge_id': pr_details["id"],
        'sha': pr_details["merge_commit_sha"],
        'author': pr_details['user']['login'] if 'login' in pr_details['user'] else pr_details['user'],
        'merged_by': pr_details['merged_by']['login'] if pr_details.get('merged_by') and 'login' in pr_details['merged_by'] else pr_details.get('merged_by'),
        'merged_at': pr_details.get('merged_at'),
        'state': pr_details['state'],
        'created_at': pr_details['created_at'],
        'updated_at': pr_details['updated_at'],
        'closed_at': pr_details.get('closed_at'),
        'title': pr_details.get('title', 'N/A'),
        'description': pr_details.get('body', 'N/A'),
        'requested_reviewers': [reviewer['login'] if 'login' in reviewer else reviewer for reviewer in pr_details.get('requested_reviewers', [])],
        'labels': [label['name'] for label in pr_details.get('labels', [])],
        'assignees': [assignee['login'] if 'login' in assignee else assignee for assignee in pr_details.get('assignees', [])],
    }
    
def get_pr_detail_bitbucket(project, repo, access_token, pr_number, endpoint):
    """
    Retrieve details of a specific pull request from Bitbucket.

    :param project: The Bitbucket owner name.
    :type project: str
    :param repo: The Bitbucket repository name.
    :type repo: str
    :param access_token: A personal access token with API permissions.
    :type access_token: str
    :param pr_number: The number of the pull request to retrieve details for.
    :type pr_number: int
    :param endpoint: Bitbucket API endpoint.
    :type endpoint: str
    :param mode: The repository service (Bitbucket).
    :type mode: str
    
    :return: Details of the specified pull request.
    :rtype: dict
    """
    # Fetch PR details
    pr_details = retrieve_pull_request_details(project, repo, access_token, pr_number, endpoint, MODE)
    if not pr_details:
        return None

    return {
        'merge_id': pr_details["id"],
        'sha': pr_details.get("toRef", {}).get("latestCommit"),  # Use the target branch's latest commit
        'author': pr_details['author']['user']['name'] if 'user' in pr_details['author'] else pr_details['author'],
        'merged_by': pr_details.get('closedBy', {}).get('name') if pr_details.get('closedBy') else None,
        'merged_at': pr_details.get('closedDate') if pr_details.get('state') == 'MERGED' else None,
        'state': pr_details['state'],
        'created_at': pr_details['createdDate'],
        'updated_at': pr_details.get('updatedDate'),
        'closed_at': pr_details.get('closedDate'),
        'title': pr_details.get('title', 'N/A'),
        'description': pr_details.get('description', 'N/A'),
        'requested_reviewers': [reviewer['user']['name'] for reviewer in pr_details.get('reviewers', [])],
        'labels': pr_details.get('labels', []),  # Bitbucket doesn't always return labels
        'assignees': [reviewer['user']['name'] for reviewer in pr_details.get('reviewers', [])],  # Use reviewers as assignees
    }


def get_pr_detail_gitlab(pull_request):
    return {
        'merge_id': pull_request["id"],
        'sha': pull_request["merge_commit_sha"],
        'author': pull_request['author']['username'] if 'username' in pull_request['author'] else pull_request['author'],
        'merged_by': pull_request['merged_by']['username'] if pull_request.get('merged_by') and 'username' in pull_request['merged_by'] else pull_request.get('merged_by'),
        'merged_at': pull_request.get('merged_at'),
        'state': pull_request['state'],
        'created_at': pull_request['created_at'],
        'updated_at': pull_request['updated_at'],
        'merged_at': pull_request['updated_at'],
        'closed_at': pull_request.get('closed_at'),
        'title': pull_request.get('title', 'N/A'),
        'description': pull_request.get('description', 'N/A',),
        'requested_reviewers': [reviewer['username'] if 'username' in reviewer else reviewer for reviewer in pull_request.get('reviewers', [])],
        'labels': pull_request.get('labels', []),
        'assignees': [assignee['username'] if 'username' in assignee else assignee for assignee in pull_request.get('assignees', [])],
    }

def get_pr_detail_azure(pull_request):
    return {
        'merge_id': pull_request["pullRequestId"],
        'sha': pull_request['lastMergeSourceCommit']['commitId'] if 'lastMergeSourceCommit' in pull_request else None,
        'author': get_user_name_azure(pull_request['createdBy']),
        'merged_by': get_user_name_azure(pull_request['closedBy']) if pull_request.get('closedBy') else None,
        'merged_at': pull_request.get('closedDate') if pull_request.get('mergeStatus') == 'completed' else None,
        'state': pull_request['status'],
        'created_at': pull_request['creationDate'],
        'updated_at': "Not/Azure",
        'closed_at': pull_request.get('closedDate', "N/A"),
        'title': pull_request.get('title', 'N/A'),
        'description': pull_request.get('description', 'N/A'),
        'requested_reviewers': [reviewer['uniqueName'] if 'uniqueName' in reviewer else reviewer for reviewer in pull_request.get('reviewers', [])],
        'labels': [label['name'] for label in pull_request.get('labels', [])],
        'assignees': [get_user_name_azure(assignee) for assignee in pull_request.get('reviewers', [])],
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
    pull_requests = retrieve_pull_requests_parallel(REPO_PATH)
elif MODE == "azure":
    pull_requests = retrieve_pull_requests_azure(OWNER, PROJECT, REPO, ACCESS_TOKEN, ENDPOINT)
    pr = []
    for group in pull_requests:
        pr.extend(group["value"])
    pull_requests = pr
elif MODE == "bitbucket":
    pull_requests = retrieve_pr_metadata_via_ls_remote(REPO_PATH)
else:
    raise ValueError(f"No settings for pr retrieval for mode {MODE}")

logging.info(f'Found {len(pull_requests)} pull requests')
# Safety Storage
# with open(storage_path, 'w') as file:
#     json.dump(pull_requests, file)
results = []
counter = 0

for pull_request in pull_requests:
    if MODE == 'github':
        pr_details = get_pr_detail_github(OWNER, REPO, ACCESS_TOKEN, pull_request['number'], ENDPOINT)
    elif MODE == 'gitlab':
        pr_details = get_pr_detail_gitlab(pull_request)
    elif MODE == 'azure':
        pr_details = get_pr_detail_azure(pull_request)
    elif MODE == 'bitbucket':
        pr_details = get_pr_detail_bitbucket(PROJECT, REPO, ACCESS_TOKEN, pull_request['number'], ENDPOINT)
    else:
        raise ValueError(f"No mode for pull request extraction: {MODE}")
    
    if not pr_details:
        continue
    
    created_at = transform_time(pr_details['created_at'])

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
    
    results.append(pr_details)
    
    counter+=1
    if counter % 100 == 0:
        logging.info(f"Processed {counter} of {len(pull_requests)} pull requests.")

# Store
df = pd.DataFrame(results)

if len(df) > 0:
    df = replace_all_user_occurences(df, REPO_PATH)
    
df.to_csv(storage_path.replace('.json', '.csv'), index=False)
