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
#======================== Helper ========================#

def welcome():
    """ Provides a welcome screen. """
    print(f'Project Generator - v:{__version__}')


def get_dst():
    """ Gets the destination folder for any copying. """
    dst = Path.cwd()
    # Check whether cwd is desired destination
    if not confirm(f'Make project at [emph]{dst}[/]?'):
        print('[failure]Exiting...')
        sys.exit()

    return dst


def declare_generation(project_type, dst):
    """ Prints a header for which type of project is being generated and the location. """
    print(f'Making [emph]{project_type}[/] Project at: [success]{dst}[/].')


def template_folder():
    return Path(__file__).parent / 'templates'


def safe_copy_tree(src, dst, ignore=None):
    """ Wrapper for shutil.copytree to check for path existence and prompt to continue. """
    if not isinstance(dst, Path): dst = Path(dst)

    if dst.exists():
        # Folder exists, prompt to continue
        if not confirm('Folder exists, overwrite?', default=False):
            # Quit the program
            sys.exit()

        # Delete the folder
        print('Deleting existing directory...')
        shutil.rmtree(dst)

    if ignore is not None: ignore = shutil.ignore_patterns(*ignore)
    shutil.copytree(src, dst, ignore=ignore)


def format_name(name):
    """ Format a general name to a standard filename convention. Converts something like "Real Analysis" to "real_analysis". """
    return name.lower().replace(' ', '_')


#======================== Project Generation ========================#


def master(dst):
    """ Generate master project. """
    print(f'Making master project at: {dst}')
    src_folder = template_folder()
    
    name = ask('[emph]Master Project name')

    master_folder = dst / format_name(name)
    safe_copy_tree(src_folder, master_folder)

    print('Master project generated.')
    itermlink.cd(master_folder)


def project(dst): pass


def scripts(dst):
    """ Generate scripts project. """
    print(f'Making Scripts project at: {dst}')
    folder = template_folder() / 'project-name/scripts'
    shutil.copytree(folder, dst / 'scripts')

    # Get iTerm session and change directory
    itermlink.cd(dst / 'scripts')


def package(dst): pass


def treatise(dst):
    """ Generate scripts project. """
    print(f'Making Treatise project at: {dst}')
    src_folder = template_folder() / 'treatise'
    
    name = ask('[emph]Project name')

    # Copy the treatise template while ignoring the .gitkeep files
    treatise_folder = dst / 'treatise'
    safe_copy_tree(src_folder, treatise_folder, ignore=['*.gitkeep'])

    with status('Cleaning files...'):
        (treatise_folder / 'subject.tex').rename(
            treatise_folder / f'{name.lower()}.tex'
        )

        (treatise_folder / 'README.md').unlink()

    print('Treatise generated.')


def exercises(dst):
    src_folder = template_folder() / 'exercises'    
    
    name = ask('[emph]Project name')

    project_folder = dst / 'exercises'
    safe_copy_tree(src_folder, project_folder, ignore=['*.gitkeep'])

    with status('Cleaning files...'):
        (project_folder / 'exercises-subject.tex').rename(
            project_folder / f'exercises-{format_name(name)}.tex'
        )

        # Delete the README file
        (project_folder / 'README.md').unlink(missing_ok=True)

    print(f'Exercises generated: [emph]{dst}[/].')



def testyaml(dst):
    with open(template_folder().parent / 'yaml_structures/exercises.yaml', 'r') as f:
        yamlfile = f.read()
    
    Filemaker(Path.cwd(), yamlfile)

#======================== Entry ========================#

def main():
    #------------- Setup -------------#
    projects = {
        #--- General Projects ---#
        # 'master': master,
        # 'project': ('Project', project),
        'Exercises': exercises,
        'YAML Test': testyaml,
        # 'scripts': scripts,
        # 'package': package,
        # 'treatise': treatise,
        #--- Teaching ---#
        # 'quizzes': quizzes,
        # 'worksheets': worksheets,
    }

    #------------- Main logic -------------#
    welcome()

    project_type = launch_filter(options=list(projects.keys()))

    # Potential output directory
    dst = get_dst()
    declare_generation(project_type, dst)
    # Run the generator at this destination
    projects[project_type](dst)

    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')