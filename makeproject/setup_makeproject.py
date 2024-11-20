#!/usr/bin/env python3
"""Handles setting up the initial configuration for makeproject, including making a structs folder with an example structure, and a templates folder with an example template.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
# import sys
#--- Custom imports ---#
from makeproject.console import *
#------------- Fields -------------#
#======================== Helper ========================#

def make_example_struct(dst):
    """ Make an example struct at dst. """
    fname = dst / 'Example.yaml'
    example_struct = (
        '# Example project structure.\n'
        '- {mp:formatted_name}:\n'
        '  - src:\n'
        '    - __init__.py\n'
        '  - tests: []\n'
        '  - README.md: <!-- The README for this project on {mp:name} -->'
    )
    with open(fname, 'w') as f:
        f.write(example_struct)


def make_structs_folder(path):
    """ Make the structs folder. Returns whether the generation was successful. """
    if not confirm(f'No structures folder found, make one at: {path}?'):
        return False
    
    # Make the directory
    path.mkdir(parents=True)
    print('[success]Structs folder generated[/].')
    make_example_struct(path)
    return True