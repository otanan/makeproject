#!/usr/bin/env python3
"""Copies project template and sets up tab for working in the project.

**Author: Jonathan Delgado**

"""
# import __init__
#------------- Imports -------------#
from pathlib import Path
import shutil
import sys
import os
from yamldirs.filemaker import Filemaker
#--- Custom imports ---#
from itermlink.tools.console import *
from itermlink.tools.typing_filter import launch as launch_filter
import itermlink
#======================== Fields ========================#
__version__ = 0.10
FILE_KEY = '$' # key for file replacements
#======================== Readers ========================#

def template_folder():
    return Path(__file__).parent / 'templates'


def get_template_contents(contents_name, project_data):
    """ Gets the contents of a template file. """
    with open(template_folder() / contents_name, 'r') as f:
        contents = f.read()

    # Parse contents
    return parse_keys(contents, project_data)


def get_struct_string(project_data):
    """ Gets the YAML struct string to generate the project. """
    structs_folder = Path(__file__).parent / 'project_structs'
    yaml_fname = project_data['type'].lower() + '.yaml'

    with open(structs_folder / yaml_fname, 'r') as f:
        struct_string = f.read()

    # Direct replacements
    return parse_keys(struct_string, project_data)

#======================== Writers ========================#

def update_from_template(path, project_data):
    """ Update the file using the corresponding template. """
    template_name = str(path.name)[len(FILE_KEY):]
    with open(path, "r+") as f:
        # Contents of file with key will be its new name if provided
        new_filename = f.read()
        f.seek(0)
        f.write(get_template_contents(template_name, project_data))
        f.truncate()

    return new_filename if new_filename != '' else template_name


#======================== Helper ========================#

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


def parse_struct_tree(dst, project_data):
    """ Runs through the constructed structure tree and replaces the file contents appropriately. """
    # Walk through project's directories
    for root, dirs, files in os.walk(dst):
        for file in files:
            # Check whether this file is intended to be updated
            if FILE_KEY in file:
                # Key found in path, get the relative path
                file = (Path(root) / file).relative_to(dst)
                print(f'Detected key: [success]{file.name}[/]... updating contents...')

                new_fname = update_from_template(file, project_data)
                rename_file(file, new_fname)


def parse_keys(raw_string, project_data):
    """ Parse string for keys such as "{name}". """
    return raw_string.replace("{name}", project_data['formatted_name'])


#======================== Messages ========================#


def welcome():
    """ Provides a welcome screen. """
    console.rule(f'Project Generator v{__version__:.2f}')


def declare_project_generation(project_data):
    """ Prints a header for which type of project is being generated and the location. """
    console.rule(
        f'Making [emph]{project_data["type"]}[/] Project at: [success]{project_data["dst"]}[/].'
    )


#======================== Queries ========================#

def get_project_type(projects):
    """ Query the user for the project type. """
    return launch_filter(options=list(projects.keys()))


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

def generate_project(project_data):
    """ Main loop function for generating the project. """
    declare_project_generation(project_data)
    # Run the generator at this destination
    project_data['generator'](project_data)
    print(f'Project [emph]{project_data["name"]}[/] generated: [success]{dst}[/].')


def exercises(project_data):
    struct_string = get_struct_string(project_data)
    try:
        Filemaker(project_data['dst'], struct_string)
    except FileExistsError as e:
        if confirm(
            'Project exists... [red]delete[/] and continue?', default=False
        ):
            shutil.rmtree(project_data['dst'] / 'exercises')
            # Run again
            exercises(project_data)

    parse_struct_tree(project_data['dst'], project_data)


def test():
    pdata = {
        'type': 'Exercises',
        'name': 'Real Analysis',
        'dst': Path.cwd(),
    }
    pdata['formatted_name'] = format_name(pdata['name'])
    exercises(pdata)
    exit()

#======================== Entry ========================#

def main():
    #------------- Setup -------------#
    # Dictionary with types of projects and their generators
    projects = {
        #--- General Projects ---#
        # 'master': master,
        # 'project': ('Project', project),
        'Exercises': exercises,
        # 'scripts': scripts,
        # 'package': package,
        # 'treatise': treatise,
        #--- Teaching ---#
        # 'quizzes': quizzes,
        # 'worksheets': worksheets,
    }

    #------------- Main logic -------------#
    test()

    welcome()

    project_data = {
        'type': get_project_type(projects),
        'name': get_project_name(),
        'formatted_name': format_name(name),
        'dst': get_destination(),
    }
    project_data['generator'] = projects['type']

    # Run the generation functions
    generate_project(project_data)

    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')