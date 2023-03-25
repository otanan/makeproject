#!/usr/bin/env python3
"""Converts yaml to a directory tree for printing.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
# import sys
#--- Custom imports ---#
# from tools.config import *
#------------- Fields -------------#
CHILD_PADDING = '' # indentation for child items
#======================== Helper ========================#

def indent_count(line):
    """ Get the indentation count of the current line text. """
    return len(line) - len(line.lstrip())


#======================== String Parsing ========================#

def remove_comments_from_line(line):
    try:
        comment_index = line.index('#')
    except ValueError as e:
        return line

    # Comment is the first item, remove everything
    if line.lstrip()[0] == '#': return ''
    # Comment trails after normal text, just remove the comment
    return line[:comment_index]


def remove_comments(struct_string):
    """ Remove comments from the structure string. """
    raw_lines = struct_string.splitlines()
    lines = []
    for line in raw_lines:
        line = remove_comments_from_line(line)
        if is_line_empty(line): continue

        lines.append(line)

    return '\n'.join(lines)


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


def adjust_for_future_children(line, future_lines):
    # Include additional bar for future children, such as item d in example
    current_indent = indent_count(line)

    for future_line in future_lines:
        future_indent = indent_count(future_line)
        # There is a future i.e. such as c
        if 0 < future_indent < current_indent:
            return line[:future_indent] + CHILD_PADDING + '│' + line[future_indent + 1:]

    return line

#======================== Main ========================#

def annotate_tree(tree):
    """ Annotates lines on the tree. """
    lines = tree.splitlines()
    width = len(max(lines, key=len))
    annotated_tree_list = []
    for line in lines:
        try:
            key_index = line.index('$')
        except ValueError:
            annotated_tree_list.append(line)
            continue

        # Remove the keys
        line = line.replace('$', '')
        padding = width - len(line)
        line += (' ' * padding) + '[emph]<-- Will be updated[/]'
        annotated_tree_list.append(line)

    return '\n'.join(annotated_tree_list)


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
        #--- Check if top-level parent item ---#
        if indent_count(line) == 0:
            tree_lines.append(line.replace('- ', ''))
            continue

        #--- Child items ---#
        tree_prefix = CHILD_PADDING

        if is_last_child_line(lines, line_num):
            tree_prefix += '└──'
        else: 
            tree_prefix += '├──'

        line = line.replace('- ', tree_prefix)

        line = adjust_for_future_children(line, lines[line_num:])
        tree_lines.append(line)

    tree = '\n'.join(tree_lines)
    tree = annotate_tree(tree)
    return tree


#======================== Entry ========================#

def main():
    from itermlink.tools.console import print as print
    struct_string = """- tester:
  - papers:
    - subject_1: []
    - to_read: []
    - $papers-README.md: README.md
  - exercises-tester:
  - exercises-tester.tex
  - preamble.sty
  - references.bib
  - intro:
    - $gitrepos.tex
    - $exercises-introduction.tex: introduction.tex
    - $nomenclature.tex
  - problem_section:
    - problem_section.tex
  - $exercises-README.md: README.md"""
    print('[emph]Original Structure String:')
    print(struct_string)
    print()
    print('[success]Converted Structure String:')
    print(struct_string_to_tree(struct_string))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard interrupt.')