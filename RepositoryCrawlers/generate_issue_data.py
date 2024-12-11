import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from helper.standard import substract_and_format_time
from helper.api_access import retrieve_issues,retrieve_issue_comments, retrieve_issue_timeline
import json
load_dotenv()

ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
OWNER = 'wse-research'  # Update with actual owner if needed
REPO = 'team-tasks'  # Update with actual repo if needed
BOT_USERS = ['dependabot-preview[bot]', 'dependabot[bot]', 'renovate[bot]']

issues = retrieve_issues(OWNER, REPO, ACCESS_TOKEN)

results = []

print(len(issues))
for issue in issues:
    if not issue or issue['user']['login'] in BOT_USERS:
        continue
    created_at = datetime.fromisoformat(issue['created_at'][:-1])
    closed_at = None if issue['closed_at'] is None else datetime.fromisoformat(issue['closed_at'][:-1])
    issue_id = issue['id']

    # Calculate time until closed
    time_until_closed = None
    if closed_at:
        time_until_closed = substract_and_format_time(created_at, closed_at)

    # Calculate time until first comment
    issue_comments = retrieve_issue_comments(OWNER, REPO, ACCESS_TOKEN, issue['number'])
    time_until_first_comment = None

    if issue_comments:
        for comment in issue_comments:
            if comment['user']['login'] not in BOT_USERS:
                first_comment_time = datetime.fromisoformat(comment['created_at'][:-1])
                time_until_first_comment = substract_and_format_time(created_at, first_comment_time)
                break
        
    issue_timeline = retrieve_issue_timeline(OWNER, REPO, ACCESS_TOKEN, issue['number'])
    timeline = []
    for time in issue_timeline:

        timeline_item = {
                'event': time['event'],
                'author': time['actor']['login'],
                'created_at': time['created_at'],
                'commit_id': time['commit_id'] if 'commit_id' in time else 'N/A'
            }
        if 'label' in time:
            timeline_item = timeline_item | {'label': time['label']['name']}
        elif 'assignee' in time:
            timeline_item = timeline_item | {'assignee': time['assignee']['login']}
        
        timeline.append(timeline_item)

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
        'time_until_first_comment': time_until_first_comment,
        'timeline': json.dumps(timeline)
    })

df = pd.DataFrame(results)
df.to_csv('issues.csv', index=False)