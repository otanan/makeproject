#!/usr/bin/env python3
"""Converts yaml to a directory tree for printing.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
# import sys
#--- Custom imports ---#
# from tools.config import *
#------------- Fields -------------#
#======================== Helper ========================#

def indent_count(line):
    """ Get the indentation count of the current line text. """
    return len(line) - len(line.lstrip())


#======================== Tree parsing ========================#

def is_line_empty(line):
    return line.strip() == '' or line.strip() == '\n'


def is_first_child_line(lines, line_num):
    """ Checks whether this is the first child item. """
    if indent_count(lines[line_num]) > indent_count(lines[line_num - 1]):
        return True

    return False


def is_last_child_line(lines, line_num):
    """ Checks whether the current line is the last item in a item in a folder, or the last item before a folder is provided. """
    # It's the very last line.
    if line_num == len(lines) - 1: return True

    # Next line is a child of this line or not in this same directory
    if indent_count(lines[line_num]) != indent_count(lines[line_num + 1]):
        return True

    return False


def remove_comments_from_line(line):
    try:
        comment_index = line.index('#')
    except ValueError as e:
        return line

    # Comment is the first item, remove everything
    if line.lstrip()[0] == '#': return ''
    # Comment trails after normal text, just remove the comment
    return line[:comment_index]


def adjust_for_future_children(line, future_lines):
    # Include additional bar for future children, such as item d in example
    current_indent = indent_count(line)

    for future_line in future_lines:
        future_indent = indent_count(future_line)
        # There is a future i.e. such as c
        if 0 < future_indent < current_indent:
            return line[:future_indent] + '│' + line[future_indent + 1:]

    return line

#======================== Main ========================#

def struct_string_to_tree(struct_string):
    """ Converts the structure string in to a directory tree, such as:
        a
        ├── b
        │   ├── d
        │   └── e
        │       ├── g
        │       └── h
        └── c
            └── f    
    """
    lines = struct_string.splitlines()
    tree_lines = []

    for line_num, line in enumerate(lines):
        line = remove_comments_from_line(line)
        # Check if all that's left is an empty line
        if is_line_empty(line): continue

        if indent_count(line) == 0: # this is a parent item
            line = line.replace('- ', '')

        elif is_last_child_line(lines, line_num):
            # Check if it's the first child
            tree_prefix = '└──'
            if is_first_child_line(lines, line_num):
                # Adjust for spacing
                tree_prefix = '  ' + tree_prefix

            line = line.replace('- ', tree_prefix)

        else: 
            line = line.replace('- ', '├──')


        line = adjust_for_future_children(line, lines[line_num:])
        tree_lines.append(line)

    return '\n'.join(tree_lines)


#======================== Entry ========================#

def main():
    pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')