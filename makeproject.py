#!/usr/bin/env python3
"""Copies project template and sets up tab for working in the project.

**Author: Jonathan Delgado**

"""
# import __init__
#------------- Imports -------------#
from pathlib import Path
import sys # exit
import os # walk
import shutil # deleting existing project folders
from yamldirs.filemaker import Filemaker # .yaml to folder structure
from datetime import datetime
#--- Custom imports ---#
from itermlink.tools.console import *
from itermlink.tools.typing_filter import launch as launch_filter
import itermlink
#======================== Fields ========================#
__version__ = 0.11
FILE_KEY = '$' # key for file replacements
STRUCT_EXT = '.yaml'
STRUCT_COMMENT = '#'
STRUCTS_FOLDER = Path(__file__).parent / 'project_structs'
TEMPLATE_FOLDER = Path(__file__).parent / 'templates'
#======================== Readers ========================#

def get_template_contents(contents_name):
    """ Gets the contents of a template file. """
    with open(TEMPLATE_FOLDER / contents_name, 'r') as f:
        return f.read()


def get_struct_string(project_type):
    """ Gets the YAML struct string to generate the project. """
    yaml_fname = project_type.lower() + '.yaml'

    with open(STRUCTS_FOLDER / yaml_fname, 'r') as f:
        return f.read()


#======================== Helper ========================#

def get_struct_options():
    """ Gets all existing project structure options. """
    structs = []
    for root, dirs, files in os.walk(STRUCTS_FOLDER):
        for file in files:
            file = Path(file)
            if STRUCT_EXT == file.suffix:
                # Prettify the structure path to suggest it as an option
                path = Path(root) / file.name
                # i.e. Teaching/Quizzes, instead of
                # project_structs/teaching/Quizzes.yaml
                name = str(
                    (Path(root) / file.stem).relative_to(STRUCTS_FOLDER)
                )

                description = None
                with open(path, 'r') as f:
                    first_line = f.readline().strip()
                    # First line is a comment, this will serve as a description
                    if first_line.startswith(STRUCT_COMMENT):
                        description = first_line[len(STRUCT_COMMENT):].strip()

                structs.append( (name, description) )
    return structs


def format_name(name):
    """ Format a general name to a standard filename convention. Converts something like "Real Analysis" to "real_analysis". """
    return name.lower().replace(' ', '_')


def rename_file(path, new_fname):
    """ Renames a file.
        
        Args:
            path (pathlib.PosixPath): the path to the file to be renamed.

            new_fname (str): the new name for the file, not its path.
    
        Returns:
            (None): none
    
    """
    path.rename(path.parent / new_fname)


def parse_struct_tree(dst):
    """ Runs through the constructed structure tree and replaces the file contents appropriately. """
    # Walk through project's directories
    files_to_update = []
    for root, dirs, files in os.walk(dst):
        for file in files:
            # Check whether this file is intended to be updated
            if FILE_KEY in file:
                # Key found in file name
                # Get the path relative to the project folder
                files_to_update.append( (Path(root) / file).relative_to(dst) )

    return files_to_update


def parse_keys(raw_string, data):
    """ Parse string for keys such as "{name}". """
    parser_legend = {
        "{mp:formatted_name}": data['formatted_name'],
        "{mp:master_fname}": data['formatted_name'],
        "{mp:name}": data['name'],
    }

    for key, val in parser_legend.items():
        raw_string = raw_string.replace(key, val)

    return raw_string

#======================== Queries ========================#

def get_project_type():
    """ Query the user for the project type. """
    structs = get_struct_options()
    desc_delim = ' - '
    # Options contain names and descriptions
    options = [
        name + desc_delim + desc if desc is not None else name
        for name, desc in structs
    ]
    result = launch_filter(options=options)

    # Parse the description out of the result
    if desc_delim in result:
        # Pull the name
        result = result.split(desc_delim)[0]
    return result


def get_project_name():
    """ Query for the project name. """
    return ask('[emph]Project name')


def get_destination():
    """ Gets the destination folder for any copying. """
    dst = Path.cwd()
    # Check whether cwd is desired destination
    if not confirm(f'Make project at [emph]{dst}[/]?'):
        print('[failure]Exiting...')
        sys.exit()

    return dst


#======================== Project Generation ========================#

def generate_project(data):
    """ Main loop function for generating the project. """
    # console.rule(
    #     f'Making [emph]{data["type"]}[/] at: '
    #     f'[success]{data["dst"]}[/].'
    # )
    
    # Get the raw structure string
    struct_string = get_struct_string(data["type"])
    # Parse the structure string for any direct replacements
    struct_string = parse_keys(struct_string, data)

    #--- Generate the project ---#
    try:
        Filemaker(data['dst'], struct_string)
    except FileExistsError as e:
        if confirm(
            'Project exists... [red]delete[/] and continue?', default=False
        ):
            shutil.rmtree(data['dst'] / 'exercises')
            # Run again
            Filemaker(data['dst'], struct_string)

    # Parse the project tree structure for any files to update
    files_to_update = parse_struct_tree(data['dst'])

    for file in files_to_update:
        print(f'Detected key: [success]{file.name}[/]... updating contents...')

        template_name = str(file.name)[len(FILE_KEY):]

        # New fname will be in the file contents if any
        with open(file, 'r') as f: contents = f.read()
        new_fname = contents if contents != '' else template_name

        # Update the file
        new_contents = parse_keys(get_template_contents(template_name), data)
        with open(file, 'w') as f: f.write(new_contents)

        rename_file(file, new_fname)


    # The newest folder is the project folder
    project_folder = max(Path(data["dst"]).glob('*/'), key=os.path.getmtime)
    print(f'Project [emph]{data["name"]}[/] generated: [success]{project_folder}[/].')

    return project_folder


#======================== Entry ========================#

def main():
    console.rule(f'Project Generator v{__version__:.2f}')
    # Get all data relevant to the project
    project_data = {
        'type': get_project_type(),
        # March 15, 2023, 11:44 PM
        'datetime': datetime.now().strftime("%B %d, %Y, %I:%M %p"),
    }
    if project_data['type'] is None:
        sys.exit()

    print(f'Generating [emph]{project_data["type"]}[/] project.')

    project_data['name'] = get_project_name()
    project_data['dst'] = get_destination()
    project_data['formatted_name'] = format_name(project_data['name'])

    project_folder = generate_project(project_data)

    # Change directory
    print('Changing directories...')
    # Open folder in finder, open in sublime text, open in iTerm
    itermlink.run_command_on_active_sess(
        f'cd "{project_folder}";'
        f'open "{project_folder}";'
        f'subl "{project_folder}";'
    )

    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')