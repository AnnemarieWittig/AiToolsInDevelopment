import subprocess
import json
import requests
import base64

URL_ENDING_PULLS = "pulls"
URL_ENDING_ISSUES = "issues"
URL_ENDING_COMMITS = "commits"
URL_ENDING_TREES = "git/trees/{tree_sha}"
URL_ENDING_BLOBS = "git/blobs/{blob_sha}"

def retrieve_via_url(owner, repo, access_token, ending, parameters={}, paginate=False):
    url = f"https://api.github.com/repos/{owner}/{repo}/{ending}"

    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {access_token}',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    all_results = []
    while url:
        response = requests.get(url, headers=headers, params=parameters)
        response.raise_for_status()  # Raise an error for bad responses
        result = response.json()

        if paginate:
            # Append the results if paginate is enabled
            if isinstance(result, list):
                all_results.extend(result)
            else:
                # If the result isn't a list, append it directly (in case of a single object response)
                all_results.append(result)
        else:
            return result

        # Get the next page URL from the 'Link' header if paginate is enabled
        if paginate and 'Link' in response.headers:
            links = response.headers['Link'].split(',')
            next_link = None
            for link in links:
                if 'rel="next"' in link:
                    next_link = link[link.find('<') + 1:link.find('>')]
                    break
            url = next_link  # Set the URL to the next page if available, otherwise None
        else:
            url = None

    return all_results if paginate else result

def grab_specific_commit(owner, repo, access_token, commit_sha):
    return retrieve_via_url(owner, repo, access_token, f"{URL_ENDING_COMMITS}/{commit_sha}")

def retrieve_workflow_runs(owner, repo, access_token):
    # Use the GitHub API to retrieve workflow runs
    workflow_runs = retrieve_via_url(owner, repo, access_token, 'actions/runs', {'per_page': 100}, paginate=True)
    return workflow_runs['workflow_runs'] 

def retrieve_issues(owner, repo, access_token):
    # Use the GitHub API to retrieve issues
    issues = retrieve_via_url(owner, repo, access_token, 'issues', {'state': 'all'}, paginate=True)
    return issues

def retrieve_issue_comments(owner, repo, access_token, issue_number):
    # Use the GitHub API to retrieve comments for a specific issue
    comments = retrieve_via_url(owner, repo, access_token, f'issues/{issue_number}/comments', paginate=True)
    return comments

def retrieve_issue_timeline(owner, repo, access_token, issue_number):
    # Use the GitHub API to retrieve the timeline for a specific issue
    timeline = retrieve_via_url(owner, repo, access_token, f'issues/{issue_number}/timeline', paginate=True)
    return timeline

def retrieve_pull_request_details(owner, repo, access_token, pr_number):
    # Use the GitHub API to retrieve pull request details
    pull_details = retrieve_via_url(owner, repo, access_token, f"pulls/{pr_number}")
    return pull_details