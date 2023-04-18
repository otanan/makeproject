#!/usr/bin/env python3
"""Handles parsing keys and information from a string.

Finds keys to replace information with, or include subprojects inside of projects.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
import re
import io # redirect stdout for executing code and capturing output
from contextlib import redirect_stdout
#--- Custom imports ---#
#------------- Fields -------------#
#======================== Helper ========================#

def _escape_reserved_re_chars(string):
    return string.replace('$', '\$').replace('/', '\/')

#======================== Main ========================#

def find_key_contents(string, start_key=None, end_key=None, key=None):
    """ Finds the contents given by a key, e.g. if start_key = '{mp:' and end_key = '}', then a string that says "Hello {mp:World}" would return 'World'. """
    if start_key == end_key == key == None:
        raise ValueError('No key provided to find key contents.')

    # Assume it's symmetric if no end key is provided
    if start_key is None: start_key = key
    if end_key is None: end_key = start_key

    if start_key not in string: return None

    # Escape reserved regex keys
    start_key = _escape_reserved_re_chars(start_key)
    end_key = _escape_reserved_re_chars(end_key)

    # The regex search query
    # (?s) allows for line breaks in string
    # (.+?) matches for anything between start and end key
    # while not returning the start or end key.
    search_query = f'(?s){start_key}(.+?){end_key}'
    
    return re.search(search_query, string)[1]


def parse_code_keys(string):
    """ Detects code strings inside of the string, executes the code string, then reinserts it into the string.
        
        Args:
            string (str): the string to parse.    
    
        Returns:
            (str): the parsed string.
    
    """
    start_key = '{mp:code='
    end_key = '/}'
    code_string = find_key_contents(
        string, start_key=start_key, end_key=end_key
    )

    # There is no code left to execute
    if code_string is None: return string

    result = run_code_string(code_string)
    
    # Use this to replace the contents
    key = f'{start_key}{code_string}{end_key}'

    parsed_string = string.replace(key, result)
    
    # Recursive call
    return parse_code_keys(parsed_string)


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
    contents = find_key_contents(start_key='{mp:', end_key='}', string=string)
    print(contents)

    string = '$$Github Repo$$'
    contents = find_key_contents(key='$$', string=string)
    print(contents)

    string = 'This is the result of my code: {mp:code=print(2**8-4 / 7)/}.'
    contents = parse_code_keys(string)
    print(contents)

    string = """
    Here's some indented text before I incorporate my code: {mp:code=
for i in range(5):
    print(i**3)
    /}.
    """
    contents = parse_code_keys(string)
    print(contents)

    string = "Here's a string without any code. I should be untouched."
    contents = parse_code_keys(string)
    print(contents)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')