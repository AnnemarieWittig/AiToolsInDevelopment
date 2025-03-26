import re
from .general_purpose import hash_string_sha256
from .git_console_access import run_git_command

def format_username(name):
    """
    Format the username by taking the first letter of the first word and the rest of the last word,
    all in lowercase, with spaces removed.
    Example: "Mario Mauer" -> "mmauer"
    """
    parts = name.split()
    if len(parts) > 1:
        formatted_name = parts[0][0].lower() + parts[-1].lower()
    else:
        formatted_name = name.lower()
    return formatted_name

def get_local_git_users(repo_path=None):
    """
    Retrieve all unique usernames and emails from local Git history.
    """
    users = {}

    # Get all unique commit authors and their emails
    git_output = run_git_command(['log', '--format=%aN <%aE>', '--all'], repo_path=repo_path)

    if git_output:
        for line in git_output.split("\n"):
            if "<" in line and ">" in line:
                name, email = line.rsplit(" <", 1)
                email = email.rstrip(">")
                formatted_name = format_username(name)  
                hashed_email = hash_string_sha256(email)
                users[formatted_name] = hashed_email  
                users[name] = hashed_email  
                users[email] = hashed_email

    return users

def replace_user_data(df, users_mapping):
    """
    Replace occurrences of usernames and emails in the dataframe with the corresponding hashed email.

    :param df: Pandas DataFrame containing data to replace.
    :param users_mapping: Dictionary {username: hashed_email}.
    :return: Modified DataFrame.
    """
    df_copy = df.copy()

    for username, hashed_email in users_mapping.items():
        pattern = rf"\b{re.escape(username)}\b"
        df_copy = df_copy.map(lambda x: re.sub(pattern, hashed_email, x, flags=re.IGNORECASE) if isinstance(x, str) else x)

    return df_copy

def replace_user_data_in_dict(data_dict, users_mapping):
    """
    Replace occurrences of usernames and emails in the dictionary with the corresponding hashed email.

    :param data_dict: Dictionary containing data to replace.
    :param users_mapping: Dictionary {username: hashed_email}.
    :return: Modified dictionary.
    """
    def replace_in_value(value, users_mapping):
        if isinstance(value, str):
            for username, hashed_email in users_mapping.items():
                pattern = rf"\b{re.escape(username)}\b"
                value = re.sub(pattern, hashed_email, value)
        elif isinstance(value, dict):
            value = replace_user_data_in_dict(value, users_mapping)
        elif isinstance(value, list):
            value = [replace_in_value(item, users_mapping) for item in value]
        return value

    return {key: replace_in_value(value, users_mapping) for key, value in data_dict.items()}

def replace_all_user_occurences(df, repo_path):
    users_mapping = get_local_git_users(repo_path)
    df = replace_user_data(df, users_mapping)
    
    return df