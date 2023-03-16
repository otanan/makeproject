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


def get_template_contents(contents_name):
    """ Gets the contents of a template file. """
    with open(template_folder() / contents_name, 'r') as f:
        return f.read()


def get_struct_string(project_type, name):
    """ Gets the YAML struct string to generate the project. """
    structs_folder = Path(__file__).parent / 'project_structs'
    with open(structs_folder / (project_type + '.yaml'), 'r') as f:
        struct_string = f.read()

    # Direct replacements
    return struct_string.replace("{name}", format_name(name))

#======================== Writers ========================#

def update_from_template(path):
    """ Update the file using the corresponding template. """
    template_name = str(path.name)[len(FILE_KEY):]
    with open(path, 'w') as f:
        f.write(get_template_contents(template_name))


#======================== Helper ========================#

def format_name(name):
    """ Format a general name to a standard filename convention. Converts something like "Real Analysis" to "real_analysis". """
    return name.lower().replace(' ', '_')


def remove_key_in_fname(path):
    """ Rename the file to remove the FILE_KEY in its name. """
    name = path.parent / str(path.name)[len(FILE_KEY):]
    path.rename(name)


def parse_struct_tree(dst):
    """ Runs through the constructed structure tree and replaces the file contents appropriately. """
    # Walk through project's directories
    for root, dirs, files in os.walk(dst):
        for file in files:
            # Check whether this file is intended to be updated
            if FILE_KEY in file:
                # Key found in path, get the relative path
                file = (Path(root) / file).relative_to(dst)
                print(f'Detected key: [success]{file.name}[/]... updating contents...')
                update_from_template(file)
                remove_key_in_fname(file)


#======================== Messages ========================#


def welcome():
    """ Provides a welcome screen. """
    print(f'Project Generator - v:{__version__}')


def declare_project_generation(project_type, dst):
    """ Prints a header for which type of project is being generated and the location. """
    print(f'Making [emph]{project_type}[/] Project at: [success]{dst}[/].')


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

def generate_project(name, dst, generator):
    """ Main loop function for generating the project. """
    declare_project_generation(name, dst)
    # Run the generator at this destination
    generator(name, dst)


def exercises(name, dst):
    struct_string = get_struct_string('exercises', name)
    try:
        Filemaker(dst, struct_string)
    except FileExistsError as e:
        if confirm(
            'Project exists... [red]delete[/] and continue?', default=False
        ):
            shutil.rmtree(dst / 'exercises')
            # Run again
            exercises(name, dst)

    parse_struct_tree(dst)


def test():
    exercises('Real Analysis', Path.cwd())
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

    project_type = get_project_type(projects)
    name = get_project_name()
    # Potential output directory
    dst = get_destination()
    # Run the generation functions
    generate_project(name, dst, projects[project_type])
    print(f'Project [emph]{name}[/] generated: [success]{dst}[/].')

    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')