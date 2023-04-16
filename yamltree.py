#!/usr/bin/env python3
"""Converts yaml to a directory tree for printing.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
#--- Custom imports ---#
from itermlink.tools.console import *
#------------- Fields -------------#
SPACE_TO_INDENT = 2 # number of spaces for a single indentation
#--- Tree Parts ---#
TREE_BRANCH =   '┣━━ '
TREE_PIPE   =   '┃   '
TREE_CHILD  =   '┗━━ '
# How much space is taken up by a tree piece
TREE_PIECE_WIDTH = len(TREE_BRANCH)
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


def is_line_empty(line):
    return line.strip() == '' or line.strip() == '\n'


#======================== Tree parsing ========================#
def get_indent(line):
    """ Gets the number of indents in a line (as spaces). """
    return len(line) - len(line.lstrip())


def get_depth(line):
    """ Gets the 'depth' of the line, i.e. a subfolder is one deeper even though as a string it may have 2 or 4 spaces of indentation further. """
    return int(get_indent(line) / SPACE_TO_INDENT)


def get_depths(lines):
    """ Get all of the depths for all lines. """
    return [ get_depth(line) for line in lines ]


def place_tree_piece(line, depth, piece):
    """ Inserts the tree piece into the line at the corresponding depth. """
    start_space = (depth - 1) * TREE_PIECE_WIDTH
    end_space = start_space + TREE_PIECE_WIDTH
    return line[:start_space] + piece + line[end_space:]


def get_piece_at_depth(line, depth):
    """ Returns the existing piece (if any) at this depth. """
    start_space = (depth - 1) * TREE_PIECE_WIDTH
    end_space = start_space + TREE_PIECE_WIDTH
    return line[start_space:end_space]


def next_depth_is_different(depth, future_depths):
    return not future_depths or future_depths[0] != depth


def swap_child_for_branch(line, depth):
    """ Swaps the tree_child piece (if it exists) for the tree_branch piece. Used for corrections. """
    if get_piece_at_depth(line, depth) == TREE_CHILD:
        return place_tree_piece(line, depth, TREE_BRANCH)

    return line


def get_substruct_strings(struct_string):
    """ Finds substructures within a structure string, i.e. top-level folders or files which aren't contained inside of other folder of the project. This corresponds to rows of the structure string without any indentation. """
    lines = struct_string.splitlines()
    num_lines = len(lines)
    depths = get_depths(lines)
    substruct_strings = []

    start_index = 0
    for i, depth in enumerate(depths[1:], start=1):
        if depth != 0: continue

        substruct_strings.append('\n'.join(lines[start_index:i]))
        start_index = i

    substruct_strings.append('\n'.join(lines[start_index:num_lines]))
    return substruct_strings


#======================== Main ========================#
def _make_tree(struct_string):
    """ Main tree generation function. Takes a (sub)structure string and converts it into a tree. """
    lines = struct_string.splitlines()
    # Indentation counts
    depths = get_depths(lines)

    #--- Remove indents ---#
    for i, line in enumerate(lines):
        lines[i] = line[SPACE_TO_INDENT:]

    #--- Realign indentations to account for pieces and first corrections ---#
    for i, line in enumerate(lines):
        depth = depths[i]
        future_depths = depths[i + 1:]

        # Skip base space
        if depth == 0: continue

        space_to_add = depth * (TREE_PIECE_WIDTH - SPACE_TO_INDENT)
        new_line = (' ' * space_to_add) + line

        # Assume all pieces are children first
        if next_depth_is_different(depth, future_depths):
            new_line = place_tree_piece(new_line, depth, TREE_CHILD)
        else:
            new_line = place_tree_piece(new_line, depth, TREE_BRANCH)

        # Testing
        lines[i] = new_line

    #--- Account for future depths ---#
    for i, line in enumerate(lines):
        # Skip accounted for pipes
        if TREE_PIPE in line: continue
        if i == 0: continue
        depth = depths[i]
        future_depths = depths[i + 1:]

        for j, future_depth in enumerate(future_depths):

            if future_depth < depth:
                line = place_tree_piece(line, future_depth, TREE_PIPE)
                # Fix previous line
                lines[i - 1] = swap_child_for_branch(
                    lines[i - 1], future_depth
                )

                next_depth = depth
                for fut_depth in future_depths[j:]:
                    if fut_depth > depth: break

                    if fut_depth < depth - 1:
                        next_depth = fut_depth 
                        break

                if fut_depth < depth: break

        lines[i] = line

    return '\n'.join(lines)


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
    print( f'Original Structure String[fail]: \n{struct_string}[/]' )
    

    # First split the structure string into all subtree strings.
    substruct_strings = get_substruct_strings(struct_string)
    # Turn them into subtrees
    subtrees = [
        _make_tree(substruct_string)
        for substruct_string in substruct_strings
    ]
    # Join into a single tree
    tree = '\n'.join(subtrees)

    # Annotate the tree
    tree = annotate_tree(tree)
    return tree


#======================== Tree Decoration ========================#
def annotate_tree(tree):
    """ Annotates lines on the tree. """
    lines = tree.splitlines()

    # List of line numbers to annotate
    lines_to_annotate = []
    #--- Replace filenames ---#
    for line_num, line in enumerate(lines):
        try:
            key_index = line.index('$')
        except ValueError:
            continue

        lines_to_annotate.append(line_num)
        # Remove the keys
        fname = ''
        if ':' in line:
            # The filename can be provided as the contents of the line
            fname = line.split(':')[1].strip()
        
        if fname:
            line = line[:key_index] + fname
        else:
            # No new filename was provided, just use the existing one
            line = line.replace('$', '')

        # Update the lines
        lines[line_num] = line

    # Annotate the lines
    width = len(max(lines, key=len))
    for line_num in lines_to_annotate:
        line = lines[line_num]

        padding = width - len(line) + 1
        line += (' ' * padding) + '[emph]<-- Contents will be generated[/]'
        lines[line_num] = line

    return '\n'.join(lines)

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