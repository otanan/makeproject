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
import yaml # reading yaml files
from yamldirs.filemaker import Filemaker # .yaml to folder structure
from datetime import datetime
import argparse
import tkinter as tk # choosing directory for project generation
from tkinter import filedialog
#--- Custom imports ---#
from console import *
import setup_makeproject
import yamltree
import parser
import tokens
#======================== Fields ========================#
ROOT = Path(__file__).parent
STRUCT_EXT = '.yaml'
STRUCT_COMMENT = '#'

#--- Default configuration ---#
CONFIG_PATH = ROOT / '../config.yaml'
STRUCTS_FOLDER = Path.home() / 'makeproject/project_structs'
TEMPLATES_FOLDER = Path.home() / 'makeproject/templates'
FILE_KEY = '$' # key for file replacements
SUBPROJECT_KEY = '$$' # key for subprojects
# For prompting the user for the project type
PROMPTER = 'inquirer'
# For opening the config file, defaults to just running open
EDITOR = 'open'
#======================== Initialization ========================#

def load_config():
    """ Load the configuration file. """
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f.read())

    # print('Configuration loaded [success]successfully.[/]')

    global STRUCTS_FOLDER, TEMPLATES_FOLDER
    STRUCTS_FOLDER = Path(config['paths']['structs']).expanduser()
    TEMPLATES_FOLDER = Path(config['paths']['templates']).expanduser()

    global PROMPTER
    PROMPTER = config['prompter']

    global EDITOR
    EDITOR = config['editor']

    global FILE_KEY, SUBPROJECT_KEY
    FILE_KEY = config['tokens']['file']
    SUBPROJECT_KEY = config['tokens']['subproject']


def get_struct_options():
    """ Gets all existing project structure options. """
    if not STRUCTS_FOLDER.is_dir():
        # Structs folder does not exist. Try to make one
        if not setup_makeproject.make_structs_folder(STRUCTS_FOLDER):
            # No folder was made
            quit()

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

    if not structs:
        # Folder has no structures
        print(f'No structures found in {STRUCTS_FOLDER}.')
        quit()

    return structs


#======================== Arguments ========================#
def _init_args():
    """ Define command-line arguments """
    parser = argparse.ArgumentParser(
        prog='MakeProject',
        description='Project generator for various projects from Python, to LaTeX, teaching, etc.',
        # epilog='Text at the bottom of help'
    )
    # Set no default function so the script will run as usual
    parser.set_defaults(func=None)

    #--- Subcommands ---#
    subparsers = parser.add_subparsers(
        title='subcommands', help='configure MakeProject'
    )

    # Open config
    config_parser = subparsers.add_parser(
        'config', help="open MakeProject's configuration file. Uses the editor provided in the configuration file, which defaults to 'open' command if none exists." 
    )
    config_parser.set_defaults(func=_open_config)

    # Open project structs
    structs_parser = subparsers.add_parser(
        'structs', help="open the project structures folder to edit existing structures." 
    )
    structs_parser.set_defaults(func=_open_structs)

    # Open project templates
    templates_parser = subparsers.add_parser(
        'templates', help="open the project templates folder to edit existing templates." 
    )
    templates_parser.set_defaults(func=_open_templates)

    keys_parser = subparsers.add_parser(
        'tokens', help="view available tokens for defining project structures and writing templates."
    )
    keys_parser.set_defaults(func=tokens.print_tokens)

    # Testing flag
    # parser.add_argument('-t', '--testing', action='store_true')

    return parser.parse_args()


#------------- Subcommands -------------#
def _open_config():
    """ Open the makeproject configuration file. """
    os.system(f'{EDITOR} {CONFIG_PATH}')

def _open_structs():
    """ Open the project structures folder. """
    open_folder_in_explorer(STRUCTS_FOLDER)

def _open_templates():
    """ Open the project templates folder. """
    open_folder_in_explorer(TEMPLATES_FOLDER)


#======================== Helper ========================#
def rename_file(path, new_fname):
    """ Renames a file.
        
        Args:
            path (pathlib.PosixPath): the path to the file to be renamed.

            new_fname (str): the new name for the file, not its path.
    
        Returns:
            (None): none
    
    """
    path.rename(path.parent / new_fname)


def open_folder_in_explorer(path):
    """ Open folder in system's file explorer. """
    os.system(f'open {path}')


#======================== Readers ========================#
def get_template_contents(template_name):
    """ Gets the contents of a template file. """
    template_path = TEMPLATES_FOLDER / template_name

    if not template_path.is_file():
        print(
            'Template not found for filename: '
            f'[failure]{template_name}[/]. '
            f'Checked path: [blue]{template_path}[/].'
        )
        quit()

    with open(template_path, 'r') as f:
        return f.read()


def get_struct_string(project_type):
    """ Gets the YAML struct string to generate the project. """
    yaml_path = STRUCTS_FOLDER / (project_type + '.yaml')
    
    if not yaml_path.is_file():
        print(
            'Structure not found for project type: '
            f'[failure]{project_type}[/]. '
            f'Checked path: [blue]{yaml_path}[/].'
        )
        quit()

    with open(yaml_path, 'r') as f:
        return f.read()


#======================== Queries ========================#
def get_project_type():
    """ Query the user for the project type. """
    def prompt_typing_filter(structs):
        # Prompt using the typing filter
        from typing_filter import launch as launch_filter
        options = [ struct[0] for struct in structs ]
        descriptions = [ struct[1] for struct in structs ]
        return launch_filter(options=options, descriptions=descriptions)

    def prompt_inquirer(structs):
        # Use the inquirer module to prompt for project type.
        import inquirer
        choices = [
            struct + ' - ' + desc
            for struct, desc in structs
        ]

        questions = [inquirer.List(
            "project",
            message="Which project do you want to generate?",
            choices=choices,
        )]
        answer = inquirer.prompt(questions)['project']
        return answer.split(' - ')[0]

    structs = get_struct_options()
    prompters = {
        'typing_filter': prompt_typing_filter,
        'inquirer': prompt_inquirer
    }
    if PROMPTER not in prompters:
        print(
            'Invalid prompter: [failure]{PROMPTER}[/] provided in configuration. '
            f'Possible prompter choices are: {prompters.keys()}.'
        )
        quit()

    # Return the result of the prompt
    project_type = prompters[PROMPTER](structs)
    if project_type is None: quit()
    return project_type


def get_project_name():
    """ Query for the project name. """
    return ask('[emph]Project name')


def get_destination():
    """ Gets the destination folder for any copying. """
    dst = Path.cwd()
    return dst # do not prompt on dst until tkinter macos bug is fixed
    # Confirm the destination
    if confirm(f'Generate project at: [emph]{dst}[/]'):
        return dst

    # Provide another destination
    # Hide the tkinter window that will popup
    tk.Tk().withdraw()
    dst = filedialog.askdirectory()
    if confirm(f'Generate project at: [emph]{dst}[/]'):
        return dst

    # No directory chosen
    quit()


def get_project_data():
    """ Gets relevant project data from the user. """
    project_data = { 'type': get_project_type() }
    print(f'Generating [emph]{project_data["type"]}[/] project.')

    project_data['name'] = get_project_name()
    project_data['dst'] = get_destination()
    return project_data


#======================== Parsers ========================#
def parse_struct_tree(dst, structure):
    """ Runs through the project structure folder tree and updates the relevant files with proper template data.
        
        Args:
            dst (pathlib.PosixPath): the path to the parent folder holding the project

            structure (dict): the project structure
    
        Returns:
            (None): none
    
    """
    # Path of files to be updated after performing walk
    files_to_update = []

    # All files/parent folders to walk through. Paths to files here will be
    # ones outside of any folders at the topmost directory of the project.
    paths = [
        list(item.keys())[0]
        for item in structure
    ]

    #------------- Walking -------------#
    for path in paths:
        # First check parents folders and loose files which will be ignored by 
        # walk
        if FILE_KEY in path:
            # Key found in file name, should be updated
            files_to_update.append(Path(path))

        for root, _, files in os.walk(path):
            for file in files:
                # Check whether this file is intended to be updated
                if FILE_KEY in file:
                    rel_path = Path(root) / file
                    files_to_update.append(rel_path)

    return files_to_update


def parse_tokens(string, data, filename=''):
    """ Parses strings for keys to update content with relevant information.
        
        Args:
            string (str): the string to parse.

            data (dict): project data relevant for parsing keys.
    
        Kwargs:
            filename (str): the name of the file whose contents this corresponds to when applicable. Used when inserting filename into the body.
    
        Returns:
            (str): the parsed string with filled in data
    
    """
    # Execute code strings before parsing other keys
    parsed_string = parser.parse_code_tokens(string)

    # Make a copy of the project data to avoid overwriting any information
    data = data.copy()
    data['filename'] = filename

    # Simple replacement, currently doesn't make use of, or need parser module
    for token in tokens.TOKENS:
        result = token['func'](data)
        parsed_string = parsed_string.replace(token['name'], result)

    return parsed_string


def get_subproject_value(struct_string):
    """ Returns Exercises if $$Exercises$$ is contained inside of the struct string. """
    return parser.find_token_contents(struct_string, token='$$')


def parse_subprojects(struct_string):
    # Subprojects will be inserted as "$$Exercises$$"
    
    # Escape from recursion, no further subprojects detected.
    if SUBPROJECT_KEY not in struct_string:
        return struct_string

    # There is a subproject
    subproject = get_subproject_value(struct_string)
    print(f'Detected subproject: [success]{subproject}[/]. Updating structure...')

    # Get the line number to match the indentation
    for line_num, line in enumerate(struct_string.splitlines()):
        if SUBPROJECT_KEY in line: break

    # Respect the indentation of the subproject
    indent = yamltree.get_indent(line)
    # Get the subproject structure string
    subproject_struct = get_struct_string(subproject)

    # Increase indentation of subproject string
    subproject_lines = subproject_struct.splitlines()
    for line_num, line in enumerate(subproject_lines):
        subproject_lines[line_num] = (' ' * indent) + line

    # Insert subproject structure into project
    lines = struct_string.splitlines()
    new_lines = []
    for line_num, line in enumerate(lines):
        if SUBPROJECT_KEY in line:
            # Found the subproject
            break

    new_lines = lines[:line_num] + subproject_lines + lines[line_num + 1:]
    struct_string = '\n'.join(new_lines)
    # Run parser again to check if there's another subproject
    return parse_subprojects(struct_string)


#======================== Project Generation ========================#

def update_project_contents(data):
    """ Runs through the project folders in the file system and updates file contents with template contents, and replaces keys with relevant data as well as renames files according to project structure instructions.
        
        Args:
            data (dict): the project data.
    
        Returns:
            (None): none
    
    """
    # Parse the project tree structure for any files to update
    files_to_update = parse_struct_tree(data['dst'], data['structure'])

    for file in files_to_update:
        print(
            f'Detected token: [success]{file.name}[/]... '
            'updating contents...'
        )

        template_name = str(file.name)[len(FILE_KEY):]

        # New fname will be in the file contents if any
        with open(file, 'r') as f: contents = f.read()
        new_fname = contents if contents else template_name

        # Update the file
        # - indicates that the file is in a folder
        template_path = Path(template_name.replace('-', '/'))
        try:
            new_contents = parse_tokens(
                get_template_contents(template_path), data,
                filename=new_fname
            )
        except FileNotFoundError as e:
            print('[failure]Error gathering template contents.')
            print(
                f'Failed to parse keys for template path: '
                f'[failure]{template_path}[/], for file: [failure]{file}[/].'
            )
            sys.exit()

        with open(file, 'w') as f: f.write(new_contents)

        rename_file(file, new_fname)


def generate_project(data):
    """ Main loop function for generating the project. """

    #------------- Getting structure -------------#
    # Get the raw structure string
    struct_string = get_struct_string(data["type"])
    struct_string = yamltree.remove_comments(struct_string)

    #------------- Parsing structure -------------#
    struct_string = parse_subprojects(struct_string)

    # Remove comments included from subprojects
    struct_string = yamltree.remove_comments(struct_string)
    print() # Padding

    # Parse the structure string for any direct replacements
    struct_string = parse_tokens(struct_string, data)

    # Store the completed structure as a proper dictionary
    data['structure'] = yaml.safe_load(struct_string)

    #------------- Project Generation -------------#
    #--- Print project structure and confirm ---#
    tree = yamltree.struct_string_to_tree(struct_string)
    print(f'Destination: [empy]{data["dst"]}[/].')
    print('Project structure:')
    print(f'[success]{tree}')
    if not confirm('Continue?'):
        quit()

    try:
        Filemaker(data['dst'], struct_string)
    # except ParserError as e:
    #     raise ParserError('Parser Error encountered. Invalid yaml formatting in project structure.')
    except FileExistsError as e:
        # Conflicting folder exists, delete it and regenerate
        print(f'Project [emph]{e.filename}[/] [warning]already exists[/].')
        if confirm(
            '[red]Delete[/] existing project and continue?',
            default=False
        ):
            # Delete the conflicting file
            shutil.rmtree(data['dst'] / e.filename)
            # Run again
            Filemaker(data['dst'], struct_string)
        else:
            quit()


    update_project_contents(data)

    print(f'[emph]{data["name"]}[/] [success]generated[/].')
    print() # padding


def open_project(struct):
    """ Runs commands through itermlink to open the session. """
    if not confirm('Open project?'):
        return
    
    for substruct in struct:
        folder = list(substruct)[0]
        open_folder_in_explorer(folder)


#======================== Entry ========================#

def main():
    args = _init_args()
    load_config()
    # launch_message = f'Project Generator [success]v{__version__}[/]'

    if args.func is not None:
        args.func()
        # Only run the subcommand
        sys.exit()

    #------------- Main logic -------------#
    # console.rule(launch_message)

    # Get all data relevant to the project
    project_data = get_project_data()
    generate_project(project_data)
    open_project(project_data['structure'])
    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')