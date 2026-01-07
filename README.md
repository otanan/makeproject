# MakeProject

MakeProject is a macOS desktop app for building project folders from YAML templates and reusable file templates. It is designed for fast iteration: define a structure once, then generate complete projects with tokens and content templates.

## Features

- Project templates stored as YAML files.
- File templates stored as real files you can edit with any text editor.
- Token substitution across YAML and file templates.
- Custom tokens managed in-app.
- Optional Python blocks inside YAML for dynamic generation.
- Preview tree before generation.
- Conflict handling when generating into existing folders.
- Automatic update checks and in-app updater.
- Theme toggle.
- Configurable template storage locations.

## Install (macOS)

1. Download the latest `MakeProject.zip` from the Releases page.
2. Unzip and move `MakeProject.app` to `~/Applications` for automatic updates.
3. Launch the app.

If the app is in a protected location, the updater will prompt you to move it to `~/Applications`.

## Quick Start

1. Open the app.
2. In the Project Templates panel, create a new template.
3. Edit the YAML in the Project YAML panel.
4. Add or edit file templates in the File Templates panel.
5. Click Generate Project and choose an output folder.

## Project Templates (YAML)

Project templates are YAML files that describe the folder structure and file contents to generate.

### Explicit syntax

```yaml
- file: README.md
  content: |
    # {mp:title}

    {mp:description}

- folder: src
  contents:
    - file: main.py
      template: main.py
    - folder: tests
```

### Implicit folder syntax

```yaml
- "Teaching - {mp:title}":
  - Quizzes.md
  - file: lesson-plan.md
    content: |
      # Lesson Plan
      {mp:description}
  - folder: resources
```

### Include another project template

```yaml
- project_template: base-web-app
```

### Python-driven items

```yaml
- python: |
    result = [
      {"file": f"Quiz {i}.tex", "content": f"\\\\section*{{Quiz {i}}}\\n"}
      for i in range(3)
    ]
```

Notes:
- Tokens are case-insensitive: `{mp:title}` and `{MP:Title}` are equivalent.
- For tokenized folder names in implicit syntax, use quotes: `"{mp:title}"`.
- The Python block must return or print a list of items in the same format as the YAML list.

## File Templates

File templates are real files stored on disk. You can edit them in any text editor.

Default location:

```
~/Library/Application Support/MakeProject/file_templates
```

Each file template can be referenced by path in YAML. For example, if you have:

```
file_templates/
  main.py
  teaching/
    quiz.tex
```

Use them like this:

```yaml
- file: main.py
  template: main.py
- file: quiz_01.tex
  template: teaching/quiz.tex
```

### Example file template

```python
#!/usr/bin/env python3
"""
{mp:title} - {mp:description}
"""

def main():
    print("Hello from {mp:title}!")

if __name__ == "__main__":
    main()
```

## Tokens

Tokens are written as `{mp:name}` and replaced during generation.

Built-in tokens:

- `title` (Project title)
- `description` (Project description)

Custom tokens:

Use the Custom Tokens panel to add your own (for example, `email`), then reference them with `{mp:email}`.
Custom tokens can also be marked as Python; the app evaluates them when referenced with `{mp:name}`.
Single-line values are treated as expressions, multi-line values are treated as blocks.

Python tokens:

Use `{mp.py: expression}` for a single expression, or `{mp.py| ... }` for a code block. The expression result is inserted as text. The block should return or print a value.

## Generating Projects

1. Click Generate Project.
2. Choose an output folder.
3. Resolve conflicts when prompted:
   - Overwrite, Merge, Keep Both, Skip, or Cancel depending on the conflict.

The app shows a progress bar while generating.

## Template Locations

You can change where project templates and file templates are stored:

- Open "Preferences..." in the MakeProject menu on macOS.
- Choose new folders and optionally move existing templates.

Default locations:

```
Project templates:
~/Library/Application Support/MakeProject/project_templates

File templates:
~/Library/Application Support/MakeProject/file_templates
```
