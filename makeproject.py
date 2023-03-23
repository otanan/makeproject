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
#--- Custom imports ---#
from itermlink.tools.console import *
from itermlink.tools.typing_filter import launch as launch_filter
import itermlink
#======================== Fields ========================#
__version__ = '0.0.1.13'
FILE_KEY = '$' # key for file replacements
SUBPROJECT_KEY = '$$' # key for subprojects
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


def get_project_data():
    """ Gets relevant project data from the user. """
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


def parse_keys(raw_string, data, filename=''):
    """ Parses strings for keys to update content with relevant information.
        
        Args:
            raw_string (str): the string to parse.

            data (dict): project data relevant for parsing keys.
    
        Kwargs:
            filename (str): the name of the file whose contents this corresponds to when applicable. Used when inserting filename into the body.
    
        Returns:
            (str): the parsed string with filled in data
    
    """
    # Parse string for keys such as "{name}".
    parser_legend = {
        "{mp:formatted_name}": data['formatted_name'],
        "{mp:master_fname}": data['formatted_name'],
        "{mp:name}": data['name'],
        "{mp:filename}": filename,
    }
    # Format the filename
    formatted_filename = str(Path(filename).stem).replace('_', ' ').capitalize()
    parser_legend["{mp:formatted_filename}"] = formatted_filename

    parsed_string = raw_string
    for key, val in parser_legend.items():
        parsed_string = parsed_string.replace(key, val)

    return parsed_string


def get_subproject_value(struct_string):
    """ Returns Exercises if $$Exercises$$ is contained inside of the struct string. """
    return struct_string.split(SUBPROJECT_KEY)[1]


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

    # The number of indentations
    indent_level = len(line) - len(line.lstrip())

    # Get the subproject structure string
    subproject_struct = get_struct_string(subproject)

    # Increase indentation of subproject string
    subproject_lines = subproject_struct.splitlines()
    for line_num, line in enumerate(subproject_lines):
        subproject_lines[line_num] = (' ' * indent_level) + line

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
        print(f'Detected key: [success]{file.name}[/]... updating contents...')

        template_name = str(file.name)[len(FILE_KEY):]

        # New fname will be in the file contents if any
        with open(file, 'r') as f: contents = f.read()
        new_fname = contents if contents else template_name

        # Update the file
        # - indicates that the file is in a folder
        template_path = Path(template_name.replace('-', '/'))
        try:
            new_contents = parse_keys(
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

    #------------- Parsing structure -------------#
    struct_string = parse_subprojects(struct_string)

    # Parse the structure string for any direct replacements
    struct_string = parse_keys(struct_string, data)

    # Store the completed structure as a proper dictionary
    data['structure'] = yaml.safe_load(struct_string)

    #------------- Project Generation -------------#
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
            print('Project generation canceled.')
            sys.exit()


    update_project_contents(data)

    # The newest folder is the project folder
    project_folder = max(Path(data["dst"]).glob('*/'), key=os.path.getmtime)
    print(f'[emph]{data["name"]}[/] generated at: [success]{project_folder}[/].')
    print() # padding

    return project_folder


def open_project(project_folder):
    """ Runs commands through itermlink to open the session. """
    command = ''

    if confirm('Open project in [success]iTerm[/]?'):
        command += f'cd "{project_folder}";'
        
    if confirm('Open project in [success]Sublime Text[/]?'):
        command += f' subl "{project_folder}";'

    if confirm('Open project in [success]Finder[/]?'):
        command += f' open "{project_folder}";'

    if command: itermlink.run_command_on_active_sess(command)


def testproject():
    """ Generates a test project. """
    
    # Get all data relevant to the project
    project_data = {
        'type': 'Exercises',
        # March 15, 2023, 11:44 PM
        'datetime': datetime.now().strftime("%B %d, %Y, %I:%M %p"),
        'name': 'Real Analysis',
        'dst': Path.home() / 'Desktop',
    }
    project_data['formatted_name'] = format_name(project_data['name'])

    print(f'Generating [emph]{project_data["type"]}[/] project.')
    print(f'Name: [emph]{project_data["name"]}[/].')
    print(f'Location: [emph]{project_data["dst"]}[/].')

    project_folder = generate_project(project_data)

    if confirm('Delete Test Project?'):
        shutil.rmtree(project_folder)
        print('Test project [warning]deleted[/].')
        return

    # Test project isn't deleted, consider opening it
    command = ''

    # if confirm('Open project in iTerm?'):
    #     command += f'cd "{project_folder}";'
        
    if confirm('Open project in Sublime Text?'):
        command += f' subl "{project_folder}";'

    if confirm('Open project in Finder?'):
        command += f' open "{project_folder}";'

    if command: itermlink.run_command_on_active_sess(command)


#======================== Entry ========================#

def main():
    _TESTING_FLAG = '--testing' in sys.argv
    launch_message = f'Project Generator v{__version__}'

    #--- Testing ---#
    if _TESTING_FLAG:
        console.rule(launch_message + ' -- [success]Testing mode[/]')
        testproject()
        return

    #------------- Main logic -------------#
    console.rule(launch_message)

    # Get all data relevant to the project
    project_data = get_project_data()
    project_folder = generate_project(project_data)
    open_project(project_folder)
    

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')