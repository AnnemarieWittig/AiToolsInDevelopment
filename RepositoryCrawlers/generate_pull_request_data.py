import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.standard import retrieve_via_url, URL_ENDING_PULLS, URL_ENDING_ISSUES

load_dotenv()

ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')

OWNER = 'dbpedia'
REPO = 'dbpedia-chatbot-backend'

def substract_and_format_time(start, end):
    time_diff = end - start
    days = time_diff.days
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    formatted_time = f"{days:02}:{hours:02}:{minutes:02}:{seconds:02}"
    return formatted_time

def calculate_till_first_comment(pr, owner, repo, skip_comments_from_author=True):
    pr_number = pr['number']
    
    created_at = datetime.fromisoformat(pr['created_at'][:-1])
    print(f"PR #{pr_number} - Created at: {created_at}")
    # Get issue comments
    issue_comments = retrieve_via_url(owner, repo, ACCESS_TOKEN, f"{URL_ENDING_ISSUES}/{pr_number}/comments")

    # Get review comments
    review_comments = retrieve_via_url(owner, repo, ACCESS_TOKEN, f"{URL_ENDING_PULLS}/{pr_number}/comments")

    # Get earliest comment time
    first_comment_time = None

    for comment in issue_comments + review_comments:
        if skip_comments_from_author and comment['user']['login'] == pr['user']['login']:
            continue
        
        comment_time = datetime.fromisoformat(comment['created_at'][:-1])
        if first_comment_time is None or (comment_time < first_comment_time and comment_time != created_at):
            first_comment_time = comment_time
            
    if first_comment_time:
        time_to_first_comment = substract_and_format_time(created_at, first_comment_time)
        return time_to_first_comment
    else:
        return None

pull_requests = retrieve_via_url(OWNER, REPO, ACCESS_TOKEN, URL_ENDING_PULLS, {'state': 'all'})
results = []

for pull_request in pull_requests:
    time_till_comment = calculate_till_first_comment(pull_request, OWNER, REPO)
    results.append({
        'pr_number': pull_request['number'],
        'title': pull_request['title'],
        'created_at': pull_request['created_at'],
        'updated_at': pull_request['updated_at'],
        'closed_at': pull_request['closed_at'],
        'time_until_closed': substract_and_format_time(datetime.fromisoformat(pull_request['created_at'][:-1]), datetime.fromisoformat(pull_request['closed_at'][:-1])),
        'time_until_first_comment': time_till_comment
    }) 

df = pd.DataFrame(results)
df.to_csv('pull_requests.csv', index=False)