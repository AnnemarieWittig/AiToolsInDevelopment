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
URL_ENDING_PULLS = "pulls"
URL_ENDING_ISSUES = "issues"
URL_ENDING_COMMITS = "commits"
ISSUE_TIMELINE="issues/{issue_number}/timeline"
ISSUE_COMMENTS="issues/{issue_number}/comments"
WORKLFOW_RUNS="actions/runs"

MAX_WORKFLOW_RUNS = 10000

logging.basicConfig(level=logging.INFO)

import requests

def retrieve_via_url(owner, repo, access_token, ending, parameters={}, paginate=True, max_retries=5, backoff_factor=2, endpoint=None, max_pages=None):
    """
    Retrieve data from a GitHub repository using the Github API.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :param ending: The URL ending to specify the type of data to retrieve (e.g., 'issues', 'pulls').
    :type ending: str
    :param parameters: Additional parameters to include in the request.
    :type parameters: dict
    :param paginate: Whether to paginate through all available pages.
    :type paginate: bool
    :param max_retries: Maximum number of retries for failed requests.
    :type max_retries: int
    :param backoff_factor: Factor by which to increase the wait time between retries.
    :type backoff_factor: int
    :return: Retrieved data from the GitHub API.
    :rtype: list or dict
    """
    if endpoint is None:
        logging.error("Endpoint cannot be None.")
        return None
    
    url = f'{endpoint}/{owner}/{repo}/{ending}'

    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {access_token}',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    all_results = []
    current_page = 1
    total_pages = None

    while url:
        try:
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, params=parameters)
                    response.raise_for_status()
                    break  # If the request is successful, exit the retry loop
                except requests.exceptions.RequestException as e:
                    if response.status_code in {502, 503, 504} or isinstance(e, requests.exceptions.ChunkedEncodingError):  # Retry for these status codes and ChunkedEncodingError
                        wait_time = backoff_factor * (2 ** attempt)
                        logging.warning(f"Error {response.status_code} encountered. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"Request failed: {e}")
                        raise
            else:
                logging.error(f"Max retries exceeded for URL: {url}")
                raise Exception(f"Failed to retrieve data after {max_retries} attempts.")

            result = response.json()
            if paginate:
                if isinstance(result, list):
                    all_results.extend(result)
                else:
                    all_results.append(result)
            else:
                return result

            if paginate and 'Link' in response.headers:
                links = response.headers['Link'].split(',')
                next_link = None
                last_link = None
                for link in links:
                    if 'rel="next"' in link:
                        next_link = link[link.find('<') + 1:link.find('>')]
                    if 'rel="last"' in link:
                        last_link = link[link.find('<') + 1:link.find('>')]
                url = next_link

                if last_link and total_pages is None:
                    total_pages = int(last_link.split('page=')[-1].split('&')[0])

                if total_pages:
                    logging.info(f"Page {current_page} of {total_pages} checked.")
                else:
                    logging.info(f"Page {current_page} checked.")

                current_page += 1
                
                if max_pages != None and max_pages == current_page:
                    return all_results
            else:
                url = None

        except KeyboardInterrupt:
            logging.warning("Process interrupted by user. Saving results to 'partial_results.json'.")
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

def retrieve_workflow_runs(owner, repo, access_token, endpoint = None, max_pages=None):
    """
    Retrieve workflow runs from a GitHub repository.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to access the repository.
    :type access_token: str
    :return: A list of workflow runs.
    :rtype: list
    """
    # Use the GitHub API to retrieve workflow runs
    workflow_runs = retrieve_via_url(owner, repo, access_token, WORKLFOW_RUNS, {'per_page': 100}, paginate=True, max_pages=max_pages, endpoint=endpoint)
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
            WORKLFOW_RUNS,
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

def retrieve_pull_request_details(owner, repo, access_token, pr_number, endpoint):
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
    :return: Details of the specified pull request.
    :rtype: dict
    """
    pull_details = retrieve_via_url(owner, repo, access_token, f"{URL_ENDING_PULLS}/{pr_number}", endpoint=endpoint)
    return pull_details

def retrieve_issues_parallel(owner, repo, access_token, endpoint):
    """
    Parallel retrieval of issues using concurrent.futures.
    Fetches the first page to determine the total number of pages from the 'Link' header,
    then issues parallel requests for all remaining pages.

    :param owner: The GitHub repository owner name.
    :type owner: str
    :param repo: The GitHub repository name.
    :type repo: str
    :param access_token: A personal access token (classic) with permissions to read issues.
    :type access_token: str
    :return: A list of all issues from the repository.
    :rtype: list

    Example usage:
        >>> issues = retrieve_issues_parallel("octocat", "Hello-World", "ghp_12345abc...")
    """
    base_url=f'{endpoint}/{owner}/{repo}/{URL_ENDING_ISSUES}'
    # base_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {access_token}',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    params = {
        'state': 'all',
        'per_page': 100
    }

    logging.info(f"Starting parallel issue retrieval for repository: {owner}/{repo}")

    # 1) Fetch the first page to get total count of pages from 'Link' header
    logging.info("Requesting the first page...")
    response = requests.get(base_url, headers=headers, params=params)
    response.raise_for_status()
    first_page_data = response.json()

    link_header = response.headers.get('Link', '')
    if not link_header:
        # No Link header indicates either a single page or no pagination needed
        logging.info("Only one page of issues returned. No pagination detected.")
        return first_page_data

    # 2) Parse 'Link' header to find the last page
    total_pages = None
    for link in link_header.split(','):
        if 'rel="last"' in link:
            last_link = link[link.find('<') + 1:link.find('>')]
            # Extract &page=N from the URL
            page_number_str = last_link.split('page=')[-1].split('&')[0]
            total_pages = int(page_number_str)
            break

    if not total_pages:
        logging.info("Could not determine the last page from the Link header. Returning first page.")
        return first_page_data

    logging.info(f"Total pages determined: {total_pages}")

    all_issues = []
    all_issues.extend(first_page_data)
    current_page = 1
    logging.info(f"Page {current_page}/{total_pages} fetched. Issues so far: {len(all_issues)}")

    # 3) Function to fetch an individual page
    def fetch_page(page_number):
        page_params = params.copy()
        page_params['page'] = page_number
        logging.debug(f"Fetching page {page_number}/{total_pages} ...")
        r = requests.get(base_url, headers=headers, params=page_params)
        r.raise_for_status()
        data = r.json()
        logging.debug(f"Finished fetching page {page_number}/{total_pages}. Items: {len(data)}")
        return data

    # 4) Fetch pages 2..total_pages in parallel
    logging.info("Beginning parallel fetch of remaining pages...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_page = {
            executor.submit(fetch_page, p): p
            for p in range(2, total_pages + 1)
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