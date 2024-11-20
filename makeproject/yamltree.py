#!/usr/bin/env python3
"""Converts yaml to a directory tree for printing.

**Author: Jonathan Delgado**

"""
#------------- Imports -------------#
#--- Custom imports ---#
from makeproject.console import *
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


def is_child_piece(depth, future_depths):
    if not future_depths: return True
    if future_depths[0] != depth: return True

    # Not a child iff there's a folder/file in the same dir
    # iff there's a matching depth before a larger one
    for fut_depth in future_depths:
        if fut_depth > depth: return True
        if fut_depth == depth: return False

    return True


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
    """ Actual tree generation. """
    lines = struct_string.splitlines()
    # Indentation counts
    depths = get_depths(lines)

    # Make a matrix of all tree children, to later connect missing columns
    tree_child_matrix = [
        [False] * (max(depths) + 1)
        for _ in lines
    ]

    #--- Remove indents and corrective spacing ---#
    for i, line in enumerate(lines):
        depth = depths[i]
        line = line[SPACE_TO_INDENT:]

        space_to_add = depth * (TREE_PIECE_WIDTH - SPACE_TO_INDENT)
        line = (' ' * space_to_add) + line
        lines[i] = line

    #--- Realign indentations to account for pieces and first corrections ---#
    for i, line in enumerate(lines):
        depth = depths[i]
        # Skip base space
        if depth == 0: continue

        future_depths = depths[i + 1:]

        if is_child_piece(depth, future_depths):
            line = place_tree_piece(line, depth, TREE_CHILD)
        else:
            line = place_tree_piece(line, depth, TREE_BRANCH)


        tree_child_matrix[i][depth] = True
        lines[i] = line

    #--- Insert pipes to connect tree children ---#    
    for i in reversed(range(len(lines))):
        if i == 0: break # nothing to do at first row

        row = tree_child_matrix[i]
        for j in range(len(row)):
            # Nothing to connect here
            if not row[j]: continue

            # Found a tree child
            # Climb backwards and insert pipes
            back_index = i - 1
            # If the above entry has a piece, we're done
            # If the above entry is deeper, then we don't want to
            # connect with it
            above_entry = tree_child_matrix[back_index][j] or (depths[back_index] < depths[i])
            # Connect with everything above
            while not above_entry:
                lines[back_index] = place_tree_piece(
                    lines[back_index], j, TREE_PIPE
                )
                tree_child_matrix[back_index][j] = True

                back_index -= 1

                # Get the information on the new above entry
                above_entry = tree_child_matrix[back_index][j] or (depths[back_index] < depths[i])

                # We're about to break out of the loop
                # Set the above entry to a branch since we've been connecting 
                # with it
                if above_entry:
                    lines[back_index] = place_tree_piece(
                        lines[back_index], j, TREE_BRANCH
                    )

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