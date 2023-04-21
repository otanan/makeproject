#!/usr/bin/env python3
"""Handles parsing tokens and information from a string.

Finds tokens to replace information with, or include subprojects inside of projects.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
import re
import io # redirect stdout for executing code and capturing output
from contextlib import redirect_stdout
#--- Custom imports ---#
from console import *
#------------- Fields -------------#
#======================== Helper ========================#

def _escape_reserved_re_chars(string):
    return string.replace('$', '\$').replace('/', '\/')

#======================== Main ========================#

def find_token_contents(string, start_token=None, end_token=None, token=None):
    """ Finds the contents given by a token, e.g. if start_token = '{mp:' and end_token = '}', then a string that says "Hello {mp:World}" would return 'World'. """
    if start_token == end_token == token == None:
        raise ValueError('No token provided to find token contents.')

    # Assume it's symmetric if no end token is provided
    if start_token is None: start_token = token
    if end_token is None: end_token = start_token

    if start_token not in string: return None

    # Escape reserved regex tokens
    # Save the original tokens for error messages
    orig_start_token = start_token
    orig_end_token = end_token
    start_token = _escape_reserved_re_chars(orig_start_token)
    end_token = _escape_reserved_re_chars(orig_end_token)

    # The regex search query
    # (?s) allows for line breaks in string
    # (.+?) matches for anything between start and end token
    # while not returning the start or end token.
    search_query = f'(?s){start_token}(.+?){end_token}'
    
    results = re.search(search_query, string)
    if results is None:
        print(f'[fail]Start token: "{orig_start_token}" found but end token: '
            f'"{orig_end_token}" missing. Could not parse token.')
        quit()

    return results[1]


def parse_code_tokens(string):
    """ Detects code strings inside of the string, executes the code string, then reinserts it into the string.
        
        Args:
            string (str): the string to parse.    
    
        Returns:
            (str): the parsed string.
    
    """
    start_token = '{mp:code='
    end_token = '/}'
    code_string = find_token_contents(
        string, start_token=start_token, end_token=end_token
    )

    # There is no code left to execute
    if code_string is None: return string

    result = run_code_string(code_string)
    
    # Use this to replace the contents
    token = f'{start_token}{code_string}{end_token}'

    parsed_string = string.replace(token, result)
    
    # Recursive call
    return parse_code_tokens(parsed_string)


def run_code_string(code_string):
    """ Executes the code string and gets the result. """
    stdout = io.StringIO()
    # Redirect stdout to capture the output of the code
    with redirect_stdout(stdout):
        exec(code_string)

    # Last character is always a line break, cut it out of result.
    return stdout.getvalue()[:-1]


#======================== Entry ========================#

def main():
    string = '{mp:Hello World}'
    contents = find_token_contents(start_token='{mp:', end_token='}', string=string)
    print(contents)

    string = '$$Github Repo$$'
    contents = find_token_contents(token='$$', string=string)
    print(contents)

    string = 'This is the result of my code: {mp:code=print(2**8-4 / 7)/}.'
    contents = parse_code_tokens(string)
    print(contents)

    string = """
    Here's some indented text before I incorporate my code: {mp:code=
for i in range(5):
    print(i**3)
    /}.
    """
    contents = parse_code_tokens(string)
    print(contents)

    string = "Here's a string without any code. I should be untouched."
    contents = parse_code_tokens(string)
    print(contents)


if __name__ == '__main__':
    try:
        main()
    except tokenboardInterrupt as e:
        print('tokenboard interrupt.')