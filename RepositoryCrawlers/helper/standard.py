import requests

URL_ENDING_PULLS = "pulls"
URL_ENDING_ISSUES = "issues"

def retrieve_via_url (owner, repo, access_token, ending, filter=None):
    url = f"https://api.github.com/repos/{owner}/{repo}/{ending}"
    if filter:
        url = f"{url}?{filter}"

    payload = {}
    headers = {
    'Accept': 'application/vnd.github+json',
    'Authorization': f'Bearer {access_token}',
    'X-GitHub-Api-Version': '2022-11-28'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    result = response.json()
    
    return result