from datetime import datetime
import logging
import re
import hashlib

# Configure logging (file or console; adjust as needed)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

"""
General utility functions for time calculation and running console commands.
"""
    
def hash_string_sha256(input_string):
    """
    Hashes the input string using SHA-256 after converting it to lowercase and encoding as UTF-8.

    :param input_string: The string to be hashed.
    :type input_string: str
    
    :return: The SHA-256 hash of the input string in hexadecimal format.
    :rtype: str
    """
    return hashlib.sha256(input_string.lower().encode('utf-8')).hexdigest()

import pandas as pd
import hashlib

def hash_string_sha256(input_string):
    return hashlib.sha256(input_string.lower().encode('utf-8')).hexdigest()

def hash_and_replace_substrings(df, column_name, voluntary_column=None):
    """
    Checks for substrings in a specified column, hashes them, and replaces all occurrences in the dataframe.
    Additionally, if a voluntary column is provided, its contents are also checked and replaced.
    
    :param df: The dataframe to process.
    :type df: pd.DataFrame
    :param column_name: The name of the column to check for substrings.
    :type column_name: str
    :param voluntary_column: An optional column to check for occurrences and replace.
    :type voluntary_column: str or None
    
    :return: The modified dataframe with substrings replaced by their hashed values.
    :rtype: pd.DataFrame
    """
    df_copy = df.copy()

    # Step 1: Create a hash mapping for `column_name` values
    hash_mapping = {}
    if column_name in df_copy.columns:
        unique_values = df_copy[column_name].dropna().astype(str).unique()
        hash_mapping = {value: hash_string_sha256(value) for value in unique_values}

        # Replace `column_name` values with their hash
        df_copy[column_name] = df_copy[column_name].replace(hash_mapping)

    # Step 2: Map voluntary_column values to the same hash from column_name
    replacement_mapping = {}
    if voluntary_column and voluntary_column in df_copy.columns:
        for index, row in df.iterrows():
            author_value = row[column_name]
            author_username_value = row[voluntary_column]
            
            if pd.notna(author_value) and pd.notna(author_username_value) and author_value in hash_mapping:
                replacement_mapping[author_username_value] = hash_mapping[author_value]

    # Step 3: Replace occurrences across the entire DataFrame using the same hash
    combined_mapping = {**hash_mapping, **replacement_mapping}
    for value, hashed_value in combined_mapping.items():
        pattern = rf"\b{re.escape(value)}\b"  # Match whole words only
        df_copy = df_copy.map(lambda x: re.sub(pattern, hashed_value, x) if isinstance(x, str) else x)

    return df_copy

def transform_time(timestr):
    """
    Transform a time string into a datetime object.

    This function attempts to parse a given time string into a datetime object using multiple common formats.
    If the string does not match any of the specified formats, it logs an error message.

    Supported formats:
    - ISO 8601: '%Y-%m-%dT%H:%M:%S.%f%z'
    - ISO 8601 without microseconds: '%Y-%m-%dT%H:%M:%S%z'
    - RFC 2822: '%a, %d %b %Y %H:%M:%S %z'
    - Custom formats:
        - '%a %b %d %H:%M:%S %Y %z'
        - '%Y-%m-%d %H:%M:%S'
        - '%Y-%m-%d %H:%M:%S.%f'
        - '%d/%m/%Y %H:%M:%S'
        - '%d-%m-%Y %H:%M:%S'
        - '%Y-%m-%dT%H:%M:%S.%f%z'
        - '%Y-%m-%dT%H:%M:%S.%f%z'
        - '%Y-%m-%dT%H:%M:%S.%f%z'
        - '%Y-%m-%dT%H:%M:%S.%f%z'

    :param timestr: The time string to be transformed.
    :type timestr: str
    :return: The corresponding datetime object if the format is recognized, otherwise the original string.
    :rtype: datetime or str
    """
    if timestr.lower() == "n/a":
        return timestr

    # Fix non-standard timezones (e.g., +01:0 → +01:00)
    timestr = re.sub(r'([+-]\d{2}):(\d{1})$', r'\1:0\2', timestr)  # Converts +01:0 to +01:00

    # Try fromisoformat first (handles many ISO 8601 formats)
    try:
        return datetime.fromisoformat(timestr)
    except ValueError:
        pass

    # Define common datetime formats
    formats = [
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%d/%m/%Y %H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
        '%a, %d %b %Y %H:%M:%S %z',
        '%a %b %d %H:%M:%S %Y %z'
    ]

    # Try parsing with each format
    for fmt in formats:
        try:
            return datetime.strptime(timestr, fmt)
        except ValueError:
            continue

    logging.error(f'No valid datetime format found for "{timestr}"')
    return timestr

def substract_and_format_time(start, end):
    """
    Calculate the difference between two datetime objects and format it as a string.

    This function calculates the time difference between two datetime objects and formats it as a string in the format "DD:HH:MM:SS".

    :param start: The start time.
    :type start: datetime
    :param end: The end time.
    :type end: datetime

    :return: The formatted time difference.
    :rtype: str
    """
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return 'n/a'
    
    time_diff = end - start
    days = time_diff.days
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    formatted_time = f"{days:02}:{hours:02}:{minutes:02}:{seconds:02}"
    return formatted_time


def get_user_name_azure(user):
    if 'uniqueName' in user and '@' in user['uniqueName']:
        return user['uniqueName']
    return user.get('displayName', 'N/A')