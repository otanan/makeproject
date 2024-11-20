#!/usr/bin/env python3
"""Token logic: defining new tokens, printing them, etc.

Token parsers should have 3 pieces of information.
(i):    The token itself, e.g. {mp:name}.
(ii):   A description of the token, e.g. the name of the project
(iii):  A parser function which handles providing the replacement string for the token. The parser function should only take in the project data for manipulating any information relevant to the project, e.g. _name(data) would return 'Linear Algebra' which might be the contents of data['name'].

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
from datetime import datetime, date
#--- Custom imports ---#
from makeproject.console import *
#------------- Fields -------------#
#======================== Token Parsers ========================#

def _name(data): return data['name']

def _formatted_name(data):
    """ Formats the name for a file-friendly name. """
    return data['name'].lower().replace(' ', '_').replace('-', '_')

def _filename(data): return data['filename']

def _master_fname(data):
    """ Formats the master name for a file-friendly name. """
    return data['name'].replace(' ', '_').replace('-', '_')

def _date(_): 
    # 24_05_16
    return str(date.today())[2:].replace('-', '_')

def _fulldate(_): 
    # January 2, 2023
    return date.today().strftime('%B %d, %Y')

def _datetime(_): return datetime.now().strftime("%B %d, %Y, %I:%M %p")


TOKENS = [
    {
        'name': '{mp:name}',
        'desc': 'The name of the project provided.',
        'func': _name,
    },
    {
        'name': '{mp:formatted_name}',
        'desc': 'The file-friendly formatted name for the project, e.g. "Linear Algebra" turns into linear_algebra.',
        'func': _formatted_name,
    },
    {
        'name': '{mp:filename}',
        'desc': 'The name of the file in consideration.',
        'func': _filename,
    },
    {
        'name': '{mp:master_name}',
        'desc': 'The (predicted) name of the "master" file. Typically taken as the first item in the project structure.',
        'func': _master_fname,
    },
    {
        'name': '{mp:date}',
        'desc': 'The current date formatted for sorting. If today is Jan. 2nd, 2023, the date is printed as "2023_01_02".',
        'func': _date,
    },
    {
        'name': '{mp:fulldate}',
        'desc': 'The current date formatted for writing. If today is Jan. 2nd, 2023, the date is printed as "January 2, 2023".',
        'func': _fulldate,
    },
    {
        'name': '{mp:datetime}',
        'desc': "The current date and time. If today's date and time is Jan. 2nd, 2023, 1:23 AM, then the date and time is printed as January 2, 2023, 01:23 AM.",
        'func': _datetime,
    },
]
#======================== Main ========================#
def print_tokens():
    for token in TOKENS:
        print(
            f'[success]{token["name"]}[/]: '
            f'{token["desc"]}'
        )
        # Padding
        print()

    # Print code token which is handled separately
    print(
        '[success]{mp:code= python_code_to_execute /}[/]: '
        'A user-definable key that runs any Python code between "{mp:code=" and "/}". Captures the output of this code, so print statements are used to generate the text that will be inserted. As an example, [success]{mp:code=print(2**8 - 1)/}[/] will replace this key with the string: 255.'
    )