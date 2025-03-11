import subprocess
import json
import requests
import time
import logging
import math
import concurrent.futures
import logging
from concurrent.futures import ThreadPoolExecutor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# BASE_URL="https://api.github.com/repos/{owner}/{repo}/{ending}"
URL_ENDING_PULLS_GITHUB = "pulls"
URL_ENDING_PULLS_GITLAB = "merge_requests"
URL_ENDING_PULLS_BITBUCKET = "pull-requests"
URL_ENDING_ISSUES = "issues"
URL_ENDING_COMMITS = "commits"
ISSUE_TIMELINE="issues/{issue_number}/timeline"
ISSUE_COMMENTS="issues/{issue_number}/comments"
WORKFLOW_RUNS_GITHUB="actions/runs"
WORKFLOW_RUNS_GITLAB="pipelines"
WORKFLOW_RUNS_AZURE="pipelines"
WORKFLOW_RUNS_BITBUCKET="pipelines"
# Azure DevOps API version
AZURE_API_VERSION = "7.1-preview.3"

MAX_WORKFLOW_RUNS = 10000

def get_pagination_headers(response, mode):
    if mode == 'github':
        return extract_github_pagination(response)
    elif mode == 'gitlab':
        return extract_gitlab_pagination(response)
    elif mode == 'azure':
        return extract_azure_pagination(response)
    elif mode == 'bitbucket':
        return extract_bitbucket_pagination(response)
    return None, None

def extract_bitbucket_pagination(response):
    """Extracts pagination info from Bitbucket API."""
    last_page = response.json().get('isLastPage', False)
    if last_page == True:
        return None, None
    next_page = response.json().get('nextPageStart')  # Bitbucket provides a 'next' URL
    total_pages = None  # Bitbucket does not provide total pages
    return next_page, total_pages

def extract_azure_pagination(response):
    """Extracts pagination information for Azure DevOps."""
    next_page = response.json().get('continuationToken')  # Azure uses continuationToken
    total_pages = None  # Azure API doesn't provide total pages upfront
    return next_page, total_pages

def extract_github_pagination(response):
    """Extracts the next page number and total pages for GitHub."""
    next_link = None
    last_link = None
    total_pages = None
    next_page = None

    if 'Link' in response.headers:
        links = response.headers['Link'].split(',')

        for link in links:
            link = link.strip()
            if 'rel="next"' in link:
                next_link = link[link.find('<') + 1:link.find('>')]
            if 'rel="last"' in link:
                last_link = link[link.find('<') + 1:link.find('>')]

        if last_link:
            try:
                total_pages = int(last_link.split('page=')[-1].split('&')[0])
                logging.debug(f"Parsed total_pages: {total_pages} from last_link: {last_link}")
            except ValueError:
                logging.debug(f"Failed to parse total pages from last_link: {last_link}")

        if next_link:
            try:
                next_page = int(next_link.split('page=')[-1].split('&')[0])
                logging.debug(f"Parsed next_page: {next_page} from next_link: {next_link}")
            except ValueError:
                logging.debug(f"Failed to parse next page from next_link: {next_link}")

    logging.debug(f"Next page: {next_page}, Total pages: {total_pages}")
    return next_page, total_pages

def extract_gitlab_pagination(response):
    """Extracts the next page number for GitLab."""
    next_page = response.headers.get('X-Next-Page')
    total_pages = response.headers.get('X-Total-Pages')
    return next_page, total_pages

import base64

def get_azure_header(token):
    auth_header = base64.b64encode(f":{token}".encode()).decode()
    return {
        'Accept': 'application/json',
        'Authorization': f'Basic {auth_header}'
    }

def get_gitlab_header(token):
    return {
            'Accept': 'application/json', 
            'Authorization': f'Bearer {token}' 
        }
    
def get_github_header(token):
        return {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }

def construct_header(mode, token):
    if mode == 'github':
        return get_github_header(token)
    elif mode == 'gitlab' or mode=='bitbucket': # they have the same header
        return get_gitlab_header(token)
    elif mode == 'azure':
        return get_azure_header(token)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

def construct_url(mode, endpoint, owner, repo, ending):
    """Constructs the appropriate URL based on the mode (GitHub/GitLab)."""
    if mode == 'github':
        return f'{endpoint}/repos/{owner}/{repo}/{ending}'
    elif mode == 'gitlab':
        return f'{endpoint}/api/v4/projects/{owner}/{ending}'
    elif mode == 'azure':
        return f'{endpoint}/{owner}/{repo}/_apis/{ending}'
    elif mode == 'bitbucket':
        return f'{endpoint}/rest/api/1.0/projects/{owner}/repos/{repo}/{ending}'
    else:
        raise ValueError(f"Unsupported mode: {mode}")

def retrieve_via_url(owner, repo, access_token, ending, parameters={}, paginate=True, max_retries=5, backoff_factor=2, endpoint=None, max_pages=None, mode='gitlab', api_version=AZURE_API_VERSION):
    if endpoint is None:
        logging.error("Endpoint cannot be None.")
        return None

    url = construct_url(mode, endpoint, owner, repo, ending)
    headers = construct_header(mode, access_token)
    if mode in {"github", "gitlab"}:
        parameters.setdefault("per_page", 100)
    elif mode == "bitbucket":
        parameters.setdefault("limit", 100)
    elif mode == "azure":
        parameters.setdefault("$top", 100)
        parameters.setdefault("api_version", api_version)

    all_results = []
    current_page = 1
    total_pages = None
    continuation_token = None
    next_page = None
    
    while url:
        try:
            for attempt in range(max_retries):
                try:
                    if mode == "azure" and continuation_token:
                        parameters["continuationToken"] = continuation_token
                    elif (mode == "github" or mode == "gitlab") and next_page:
                        parameters["page"] = next_page
                    elif (mode == "bitbucket") and next_page:
                        parameters["start"] = next_page
                    logging.debug(parameters)
                    response = requests.get(url, headers=headers, params=parameters)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if response.status_code in {502, 503, 504}:
                        wait_time = backoff_factor * (2 ** attempt)
                        logging.debug(f"Error {response.status_code}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"Request failed: {e}")
                        raise
            else:
                logging.error(f"Max retries exceeded for URL: {url}")
                raise Exception(f"Failed to retrieve data after {max_retries} attempts.")

            result = response.json()
            if paginate:
                if mode == "bitbucket":
                    if "values" in result:
                        all_results.extend(result["values"])
                    else:
                        logging.debug("Bitbucket response did not contain 'values'. Check API response format.")
                else:
                    all_results.extend(result if isinstance(result, list) else [result])
            else:
                return result

            if mode == "azure":
                continuation_token = response.headers.get("x-ms-continuationtoken")
                url = construct_url(mode, endpoint, owner, repo, ending) if continuation_token else None
            else:
                next_page, total_pages = get_pagination_headers(response, mode)
                url = construct_url(mode, endpoint, owner, repo, ending) if next_page else None

            if continuation_token or next_page:
                if total_pages:
                    logging.info(f"Page {current_page} of {total_pages} checked.")
                else:
                    logging.info(f"Page {current_page} checked.")

            current_page += 1
            if max_pages and current_page == max_pages:
                logging.info(f"All {current_page} pages checked.")
                return all_results

        except KeyboardInterrupt:
            logging.debug("Process interrupted by user. Saving results to 'partial_results.json'.")
            with open('partial_results.json', 'w') as f:
                json.dump(all_results, f, indent=4)
            raise
    
    return all_results if paginate else result

def grab_specific_commit(owner, repo, access_token, commit_sha):
    """
    Retrieve details of a specific commit from a GitHub repository.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :param commit_sha: The SHA of the commit to retrieve.
    :type commit_sha: str
    :return: Details of the specified commit.
    :rtype: dict
    """
    return retrieve_via_url(owner, repo, access_token, f"{URL_ENDING_COMMITS}/{commit_sha}")

def retrieve_workflow_runs(owner, repo, access_token, endpoint=None, max_pages=None, mode='github'):
    """
    Retrieve workflow runs from GitHub, GitLab, Azure, or Bitbucket.
    """
    if mode == 'github':
        ending = WORKFLOW_RUNS_GITHUB
    elif mode == 'gitlab':
        ending = WORKFLOW_RUNS_GITLAB
    elif mode == 'azure':
        ending = WORKFLOW_RUNS_AZURE
    elif mode == 'bitbucket':
        ending = WORKFLOW_RUNS_BITBUCKET
    else:
        raise ValueError(f"No handling for mode {mode} available")
    
    workflow_runs = retrieve_via_url(owner, repo, access_token, ending, paginate=True, max_pages=max_pages, endpoint=endpoint, mode=mode, api_version="5.1")
    runs = []

    if mode == "gitlab" or mode == "azure" or mode == "bitbucket":
        return workflow_runs

    runs = []
    for run in workflow_runs:
        runs.extend(run['workflow_runs'])
    
    return runs


def retrieve_all_workflow_runs_parallel(owner, repo, access_token):
    """
    Retrieve all workflow runs from a GitHub repository in parallel using the Github API.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :return: A list of all workflow runs.
    :rtype: list
    """
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        # Use pagination to retrieve all pages of workflow runs
        futures.append(executor.submit(
            retrieve_via_url,
            owner,
            repo,
            access_token,
            None,
            {'per_page': 100},  # Adjust per_page as needed
            True
        ))
        for future in futures:
            results.extend(future.result())
            
    return results

def retrieve_issues(owner, repo, access_token):
    """
    Retrieve issues from a GitHub repository using the Github API.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :return: A list of issues.
    :rtype: list
    """
    issues = retrieve_via_url(owner, repo, access_token, 'issues', {'state': 'all'}, paginate=True)
    return issues

def retrieve_issue_comments(owner, repo, access_token, issue_number):
    """
    Retrieve comments for a specific issue from a GitHub repository using the Github API.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :param issue_number: The number of the issue to retrieve comments for.
    :type issue_number: int
    :return: A list of comments for the specified issue.
    :rtype: list
    """
    # Use the GitHub API to retrieve comments for a specific issue
    # Request 'per_page=100' so fewer pages are needed.
    parameters = {'per_page': 100}
    comments = retrieve_via_url(
        owner,
        repo,
        access_token,
        ISSUE_COMMENTS.format(issue_number=issue_number),
        parameters=parameters,
        paginate=True
    )
    return comments


def retrieve_issue_timeline(owner, repo, access_token, issue_number):
    """
    Retrieve the timeline for a specific issue from a GitHub repository.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :param issue_number: The number of the issue to retrieve the timeline for.
    :type issue_number: int
    :return: The timeline of the specified issue.
    :rtype: list
    """
    timeline = retrieve_via_url(owner, repo, access_token, ISSUE_TIMELINE.format(issue_number=issue_number), paginate=True)
    return timeline

def retrieve_pull_request_details(owner, repo, access_token, pr_number, endpoint, mode):
    """
    Retrieve details of a specific pull request from a GitHub repository.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :param pr_number: The number of the pull request to retrieve details for.
    :type pr_number: int
    :param mode: Specifies whether to retrieve from "github" or "gitlab".
    :type mode: str
    
    :return: Details of the specified pull request.
    :rtype: dict
    """
    if mode == "github":
        ending = f"{URL_ENDING_PULLS_GITHUB}/{pr_number}"
    elif mode == "bitbucket":
        ending = f"{URL_ENDING_PULLS_BITBUCKET}/{pr_number}"
    
    pull_details = retrieve_via_url(owner, repo, access_token, ending, endpoint=endpoint, mode=mode)
    return pull_details

def retrieve_issues_parallel(owner, repo, access_token, endpoint, mode):
    """
    Parallel retrieval of issues using concurrent.futures.
    Fetches the first page to determine the total number of pages using pagination headers,
    then issues parallel requests for all remaining pages.

    :param owner: The GitHub or GitLab repository owner name.
    :param repo: The GitHub repository name (GitLab uses project ID).
    :param access_token: A personal access token with permission to read issues.
    :param endpoint: API base URL.
    :param mode: Specifies whether to retrieve from "github" or "gitlab".
    
    :return: A list of all issues from the repository.
    """

    # Determine API URL and headers based on mode
    if mode == "github":
        base_url = f'{endpoint}/repos/{owner}/{repo}/{URL_ENDING_ISSUES}'
        headers = get_github_header(access_token)
    elif mode == "gitlab":
        base_url = f'{endpoint}/api/v4/projects/{owner}/{URL_ENDING_ISSUES}'
        headers = get_gitlab_header(access_token)
    elif mode == "azure":
        return retrieve_issues_parallel_azure(owner, repo, access_token, endpoint)
    else:
        raise ValueError(f"Unsupported mode: {mode}. Choose 'github', 'azure' or 'gitlab'.")

    params = {
        'state': 'all',
        'per_page': 100  # Max per page
    }

    logging.info(f"Starting parallel issue retrieval for repository: {owner}/{repo}")

    # 1) Fetch the first page to get pagination details
    logging.info("Requesting the first page...")
    response = requests.get(base_url, headers=headers, params=params)
    response.raise_for_status()
    first_page_data = response.json()

    # Use pagination function to extract next page & total pages
    next_page, total_pages = get_pagination_headers(response, mode)

    if not total_pages:
        logging.info("Only one page of issues returned. No pagination detected.")
        return first_page_data

    logging.info(f"Total pages determined: {total_pages}")

    all_issues = first_page_data.copy()
    logging.info(f"Page 1/{total_pages} fetched. Issues so far: {len(all_issues)}")

    # 2) Function to fetch an individual page
    def fetch_page(page_number):
        """Fetch issues from a specific page."""
        page_params = params.copy()
        if mode == "github":
            page_params['page'] = page_number
        elif mode == "gitlab":
            page_params['page'] = page_number

        logging.debug(f"Fetching page {page_number}/{total_pages} ...")
        r = requests.get(base_url, headers=headers, params=page_params)
        r.raise_for_status()
        data = r.json()
        logging.debug(f"Finished fetching page {page_number}/{total_pages}. Items: {len(data)}")
        return data

    # 3) Fetch remaining pages in parallel
    logging.info("Beginning parallel fetch of remaining pages...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_page = {
            executor.submit(fetch_page, p): p for p in range(2, int(total_pages) + 1)
        }

        for future in concurrent.futures.as_completed(future_to_page):
            page_num = future_to_page[future]
            try:
                page_data = future.result()
                all_issues.extend(page_data)
                logging.info(f"Page {page_num}/{total_pages} fetched. "
                             f"Total issues accumulated: {len(all_issues)}")
            except Exception as e:
                logging.error(f"Failed to fetch page {page_num}. Error: {e}")

    logging.info(f"Finished retrieving all {len(all_issues)} issues from {owner}/{repo}")
    return all_issues

def retrieve_issues_parallel_azure(organization, project, personal_access_token, endpoint):
    """
    Retrieves all work items (issues) from an Azure DevOps project in parallel.

    :param organization: The Azure DevOps organization name.
    :param project: The Azure DevOps project name.
    :param personal_access_token: Personal access token with work item read permissions.
    :param endpoint: Azure DevOps API base URL.
    
    :return: A list of all work items with their details.
    """

    # Base URL for Azure DevOps
    base_url = f"{endpoint}/{organization}/{project}/_apis/wit"
    headers = get_azure_header(personal_access_token)

    logging.info(f"Fetching all work items for project: {project}")

    # 1) Fetch all work item IDs using a Wiql query
    logging.info("Executing Wiql query to retrieve all work item IDs...")

    wiql_url = f"{base_url}/wiql?api-version=5.1"
    wiql_query = {
        "query": "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project"
    }

    response = requests.post(wiql_url, headers=headers, json=wiql_query)
    response.raise_for_status()
    work_items = response.json().get("workItems", [])

    if not work_items:
        logging.info("No work items found.")
        return []

    # Extract IDs
    work_item_ids = [str(item["id"]) for item in work_items]
    logging.info(f"Total work items retrieved: {len(work_item_ids)}")

    # 2) Fetch full details of work items in batches (Azure limits request size)
    BATCH_SIZE = 200  # Maximum allowed batch size in Azure API
    all_issues = []

    def fetch_work_items_batch(batch_ids):
        """Fetches a batch of work item details from Azure DevOps."""
        url = f"{base_url}/workitems?ids={','.join(batch_ids)}&api-version={AZURE_API_VERSION}"
        logging.debug(f"Fetching batch: {batch_ids}")
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        return r.json().get("value", [])

    logging.info(f"Fetching full details for {len(work_item_ids)} work items in parallel...")

    # 3) Fetch work items in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_batch = {
            executor.submit(fetch_work_items_batch, work_item_ids[i:i+BATCH_SIZE]): i
            for i in range(0, len(work_item_ids), BATCH_SIZE)
        }

        for future in concurrent.futures.as_completed(future_to_batch):
            try:
                batch_data = future.result()
                all_issues.extend(batch_data)
                logging.info(f"Fetched {len(batch_data)} additional work items.")
            except Exception as e:
                logging.error(f"Failed to fetch batch. Error: {e}")

    logging.info(f"Finished retrieving all {len(all_issues)} work items from {project}")
    return all_issues

def retrieve_oldest_comments_parallel(owner, repo, access_token, issues, max_workers=5):
    """
    Retrieves the oldest human (non-bot) comment for multiple issues in parallel.
    
    :param owner: GitHub repo owner.
    :param repo: GitHub repo name.
    :param access_token: GitHub personal access token.
    :param issues: List of issue objects or dictionaries that include an 'number' field.
    :param max_workers: Concurrency factor. Adjust upward or downward based on rate limits.
    :return: Dictionary mapping issue_number -> oldest non-bot comment dict (or None if none).
    """
    issue_numbers = [issue['number'] for issue in issues]

    # Helper function for concurrency
    def fetch_for_issue(issue_number):
        return (issue_number, retrieve_oldest_comment(owner, repo, issue_number, access_token))

    comments_dict = {}
    total_issues = len(issue_numbers)
    logging.info(f"Starting parallel retrieval of oldest comments for {total_issues} issues.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_issue = {
            executor.submit(fetch_for_issue, num): num
            for num in issue_numbers
        }
        for i, future in enumerate(concurrent.futures.as_completed(future_to_issue), start=1):
            num = future_to_issue[future]
            try:
                issue_num, c = future.result()
                comments_dict[issue_num] = c
            except Exception as e:
                logging.error(f"Failed to retrieve oldest comment for issue #{num}. Error: {e}")

            # Periodic progress logging
            if i % 100 == 0:
                logging.info(f"Processed {i} of {total_issues} issues...")

    logging.info("Parallel oldest comment retrieval complete.")
    return comments_dict

def retrieve_oldest_comment(owner, repo, issue_number, access_token):
    """
    Returns the oldest (first) comment on a GitHub issue using the GitHub REST API.
    """
    base_url = BASE_URL.format(owner=owner,repo=repo,ending=ISSUE_COMMENTS.format(issue_number=issue_number))# f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {access_token}',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    # Request only the first comment (oldest) by sorting ascending
    params = {
        'sort': 'created',
        'direction': 'asc',
        'per_page': 5
    }

    response = requests.get(base_url, headers=headers, params=params)
    response.raise_for_status()
    comments = response.json()
    return comments[0] if comments else None

def retrieve_pull_requests_gitlab(project_id, access_token, endpoint, max_workers=5):
    """
    Retrieve merge requests (MRs) from a GitLab repository using the GitLab API.

    :param project_id: GitLab project ID (stored as OWNER in scripts).
    :type project_id: str
    :param access_token: GitLab personal access token.
    :type access_token: str
    :param endpoint: GitLab API endpoint.
    :type endpoint: str
    :param max_workers: Maximum number of threads to use for parallel processing, defaults to 5.
    :type max_workers: int, optional

    :return: A list of dictionaries containing merge request information, structured like GitHub PRs.
    :rtype: list
    """
    # Fetch all MRs using the GitLab API
    logging.info("Retrieving merge requests from GitLab...")
    merge_requests = retrieve_via_url(project_id, None, access_token, 'merge_requests', endpoint=endpoint, mode='gitlab')

    if not merge_requests:
        logging.debug("No merge requests found.")
        return []

    total_refs = len(merge_requests)
    logging.info(f"Found {total_refs} merge requests.")
    
    # Process MRs in parallel
    # pull_requests = []
    # with ThreadPoolExecutor(max_workers=max_workers) as executor:
    #     future_to_mr = {
    #         executor.submit(process_single_mr, mr): mr for mr in merge_requests
    #     }

    #     for i, future in enumerate(future_to_mr, start=1):
    #         mr = future_to_mr[future]
    #         try:
    #             mr_data = future.result()
    #             if mr_data:
    #                 pull_requests.append(mr_data)
    #         except Exception as e:
    #             logging.error(f"Failed to process MR {mr['id']}: {e}")

    #         if i % 100 == 0 or i == total_refs:
    #             logging.info(f"Processed {i} of {total_refs} merge requests...")

    # logging.info(f"Finished processing all {total_refs} merge requests.")
    return merge_requests

def retrieve_pull_requests_azure(owner, project, repo, access_token, endpoint):
    """
    Retrieve raw pull requests from an Azure DevOps repository using the Azure DevOps REST API in parallel.

    :param owner: Azure DevOps organization name.
    :type owner: str
    :param project: Azure DevOps project name.
    :type project: str
    :param repo: Azure DevOps repository name.
    :type repo: str
    :param access_token: Azure DevOps personal access token.
    :type access_token: str
    :param endpoint: Azure DevOps API endpoint.
    :type endpoint: str
    :param max_workers: Maximum number of threads to use for parallel retrieval, defaults to 5.
    :type max_workers: int, optional

    :return: A list of raw pull request dictionaries.
    :rtype: list
    """
    logging.info("Retrieving pull requests from Azure DevOps...")
    
    repo = f"{repo}.git" if not ".git" in repo else repo

    # Construct the API path for pull requests within a repository
    api_path = f"git/repositories/{repo}/pullrequests"

    api_version = "7.1"

    # Fetch all pull requests using the Azure DevOps API
    pull_requests = retrieve_via_url(owner, project, access_token, api_path,
                                    endpoint=endpoint, mode='azure', api_version=api_version, 
                                    parameters={"searchCriteria.status": "all"})

    if not pull_requests:
        logging.debug("No pull requests found.")
        return []
    
    return pull_requests

def process_single_mr(mr):
    """
    Process a single merge request (MR) to normalize its data for consistency with GitHub PRs.

    :param mr: A dictionary containing merge request metadata.
    :type mr: dict
    :param repo_path: Path to the local Git repository.
    :type repo_path: str

    :return: A dictionary containing normalized merge request information.
    :rtype: dict
    """
    return {
        'number': mr['iid'],
        'author': mr['author']['username'],
        'merger': mr['merged_by']['username'] if mr.get('merged_by') else None,
        'state': mr['state'],
        'created_at': mr['created_at'],
        'updated_at': mr['updated_at'],
        'closed_at': mr.get('closed_at'),
        'merged_at': mr.get('merged_at'),
        'title': mr.get('title', 'N/A'),
        'requested_reviewers': [reviewer['username'] for reviewer in mr.get('reviewers', [])] if 'reviewers' in mr else [],
        'labels': mr.get('labels', []),
        'assignees': [assignee['username'] for assignee in mr.get('assignees', [])],
    }