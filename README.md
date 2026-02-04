# MakeProject

MakeProject is a macOS desktop app for building project folders from YAML templates and reusable file templates. It is designed for fast iteration: define a structure once, then generate complete projects with tokens and content templates.

## Features

- Project templates stored as YAML files
- File templates stored as real files you can edit with any text editor
- **Folder templates** - insert entire groups of files with a single reference
- **Binary file support** - use images, PDFs, and other binary files as templates
- Token substitution across YAML and file templates
- Custom tokens managed in-app
- Optional Python blocks inside YAML for dynamic generation
- Python-backed custom tokens (same `{mp:token}` syntax)
- Preview tree before generation
- Conflict handling when generating into existing folders
- **Keyboard shortcuts** - Cmd+Enter to generate, Cmd+F to search templates
- Automatic update checks and in-app updater
- Theme toggle
- Configurable template storage locations
- Roadmap: https://otanan.notion.site/makeproject

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
5. Press **Cmd+Enter** to generate the project (or click Generate Project).

## Keyboard Shortcuts

- **Cmd+Enter** - Generate project
- **Cmd+F** - Search templates
- **Cmd+N** - New project template
- **Cmd+S** - Save current template
- **Cmd+Z/Shift+Z** - Undo/Redo
- **Cmd++/Cmd+-** - Increase/Decrease font size

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
    - file_template: main.py
    - folder: tests
```

### File template shorthand

`file_template` uses the same name for both the file and its template:

```yaml
- file_template: config.json  # Creates "config.json" using the "config.json" template
```

When the template is in a folder, only the basename is used:

```yaml
- file_template: python/main.py  # Creates "main.py" using the "python/main.py" template
```

### Folder templates

Use `folder_template` to insert all files from a template folder at once:

```yaml
- folder_template: boilerplate  # Inserts all files from the "boilerplate" folder
```

Or use the `template` property on a folder to populate it:

```yaml
- folder: src
  template: python-project  # Populates "src" with all files from "python-project" folder
```

This is equivalent to:

```yaml
- src:
  - folder_template: python-project
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
  title: {mp:title} API
  description: Backend portion of {mp:title}.
```

You can override `title` and `description` when including another project template.

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
  logo.png
  teaching/
    quiz.tex
    handout.pdf
```

Use them like this:

```yaml
- file: main.py
  template: main.py
- file: quiz_01.tex
  template: teaching/quiz.tex
- file_template: logo.png  # Binary files are copied as-is
- file_template: teaching/handout.pdf
```

### Binary files

Binary files (images, PDFs, documents, etc.) are automatically detected by extension and copied without token substitution:

**Supported binary formats:**
- Images: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.ico`, `.svg`
- Documents: `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`
- Archives: `.zip`, `.tar`, `.gz`, `.bz2`, `.7z`, `.rar`
- Media: `.mp3`, `.mp4`, `.avi`, `.mov`, `.wav`, `.flac`
- Fonts: `.ttf`, `.otf`, `.woff`, `.woff2`
- Databases: `.db`, `.sqlite`, `.sqlite3`

Text files support token substitution:

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

### Organizing with folders

Organize file templates into folders for better organization:

```
file_templates/
  web/
    index.html
    style.css
    script.js
  python/
    main.py
    requirements.txt
    __init__.py
```

Right-click a folder and select **"Generate this folder"** to generate all templates in that folder to a chosen directory.

## Tokens

Tokens are written as `{mp:name}` and replaced during generation.

Built-in tokens:

- `title` (Project title)
- `description` (Project description)

Context dict keys (available in Python tokens as `context["key"]`):

- `title`, `description` (built-in)
- Custom tokens by name (case-insensitive)
- File-scoped keys for file content and file templates only: `filename` (e.g. `foo.txt`), `file_stem` (e.g. `foo`), `file_ext` (e.g. `.txt`)

All keys are added with lowercase aliases for case-insensitive lookups.

Custom tokens:

Use the Custom Tokens panel to add your own (for example, `email`), then reference them with `{mp:email}`.
Custom tokens can also be marked as Python; the app evaluates them when referenced with `{mp:name}` (same syntax as text tokens).
Single-line Python values are treated as expressions, multi-line values are treated as blocks.

Python tokens:

Use `{mp.py: expression}` for a single expression, or `{mp.py} ... {/mp.py}` for a code block. The expression result is inserted as text. The block should return or print a value.

## Python Settings

The Settings window includes a Python Settings tab:

- Python interpreter path (defaults to the app's Python interpreter).
- Python Preamble: code that runs before every Python expression or block during generation, so you can define helpers or shared variables.

## Generating Projects

1. Press **Cmd+Enter** (or click Generate Project).
2. Choose an output folder.
3. Resolve conflicts when prompted:
   - **Overwrite**, **Merge**, **Keep Both**, **Skip**, or **Cancel** depending on the conflict.
   - Check **"Apply to all"** to use the same decision for all remaining conflicts.

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

## Examples

### Example 1: Simple Python Project

**Project Template (simple-python):**
```yaml
- file: README.md
  content: |
    # {mp:title}

    {mp:description}

    ## Installation

    ```bash
    pip install -r requirements.txt
    ```

- file_template: main.py
- file_template: requirements.txt
- folder: tests
  contents:
    - file: __init__.py
    - file: test_main.py
      content: |
        import pytest
        from main import main

        def test_main():
            assert main() is not None
```

**File Template (main.py):**
```python
#!/usr/bin/env python3
"""
{mp:title}

{mp:description}

Author: {mp:email}
"""

def main():
    """Main entry point."""
    print("Hello from {mp:title}!")
    return 0

if __name__ == "__main__":
    main()
```

**File Template (requirements.txt):**
```
pytest>=7.0.0
```

**Custom Token:**
- `email` = "yourname@example.com"

**Result:** Press Cmd+Enter, choose output folder, and get a complete Python project with tests!

### Example 2: Web Project with Assets

**File Templates (web folder):**
```
file_templates/
  web/
    index.html
    style.css
    script.js
  assets/
    logo.png
    favicon.ico
```

**Project Template:**
```yaml
- file_template: web/index.html
- file_template: web/style.css
- file_template: web/script.js
- folder: assets
  template: assets  # Populates with logo.png and favicon.ico
```

**File Template (web/index.html):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{mp:title}</title>
    <link rel="stylesheet" href="style.css">
    <link rel="icon" href="assets/favicon.ico">
</head>
<body>
    <header>
        <img src="assets/logo.png" alt="{mp:title} Logo">
        <h1>{mp:title}</h1>
    </header>
    <main>
        <p>{mp:description}</p>
    </main>
    <script src="script.js"></script>
</body>
</html>
```

The binary files (logo.png, favicon.ico) are copied as-is without token processing.

### Example 3: Teaching Materials with Python

**Project Template (course-module):**
```yaml
- folder: "{mp:title}"
  contents:
    - file: syllabus.md
      content: |
        # {mp:title}

        {mp:description}

        ## Instructor
        {mp:instructor}

        ## Schedule
        {mp.py:
          weeks = int(context.get("weeks", 12))
          "\n".join([f"- Week {i}: TBD" for i in range(1, weeks + 1)])
        }

    - python: |
        num_quizzes = int(context.get("num_quizzes", 3))
        result = [
          {"file": f"quiz-{i:02d}.tex", "template": "teaching/quiz.tex"}
          for i in range(1, num_quizzes + 1)
        ]

    - folder: handouts
      template: teaching/handouts

    - folder: solutions
```

**File Template (teaching/quiz.tex):**
```latex
\documentclass{article}
\usepackage[utf8]{inputenc}

\title{{mp:title} - Quiz}
\author{{mp:instructor}}
\date{\today}

\begin{document}

\maketitle

\section*{Instructions}
Answer all questions. Show your work.

% Questions go here

\end{document}
```

**Custom Tokens:**
- `instructor` = "Dr. Smith"
- `weeks` = "12"
- `num_quizzes` = "5"

**Result:** Generates a complete course module with syllabus, multiple quiz files, handouts folder populated from templates, and solutions folder.

### Example 4: Multi-Repository Setup

**Project Template (fullstack-app):**
```yaml
- folder: backend
  contents:
    - project_template: python-api
      title: {mp:title} API
      description: Backend for {mp:title}

- folder: frontend
  contents:
    - project_template: react-app
      title: {mp:title} UI
      description: Frontend for {mp:title}

- folder: shared
  contents:
    - folder_template: config  # Shared config files

- file: docker-compose.yml
  content: |
    version: '3.8'
    services:
      backend:
        build: ./backend
        ports:
          - "8000:8000"
      frontend:
        build: ./frontend
        ports:
          - "3000:3000"

- file: README.md
  content: |
    # {mp:title}

    {mp:description}

    ## Getting Started

    ```bash
    docker-compose up
    ```
```

This creates a complete full-stack application with separate backend and frontend folders, each populated from their own project templates, plus shared configuration and Docker setup.

### Example 5: Report with LaTeX and Data

**Project Template (research-report):**
```yaml
- folder: "{mp:title}-report"
  contents:
    - file_template: latex/report.tex
    - file_template: latex/references.bib

    - folder: figures
      contents:
        - file_template: figures/graph.png
        - file_template: figures/diagram.pdf

    - folder: data
      contents:
        - file: dataset.csv
          content: |
            {mp.py:
              import random
              rows = ["x,y"]
              for i in range(10):
                  x = i
                  y = random.randint(0, 100)
                  rows.append(f"{x},{y}")
              "\n".join(rows)
            }

    - file: Makefile
      content: |
        report.pdf: report.tex references.bib
        	pdflatex report.tex
        	bibtex report
        	pdflatex report.tex
        	pdflatex report.tex

        clean:
        	rm -f *.aux *.log *.bbl *.blg *.out
```

This generates a complete LaTeX report with figures (binary files copied as-is), dynamically generated data, and a Makefile for compilation.

## Tips

- **Search templates** - Press Cmd+F to quickly find project or file templates
- **Organize with folders** - Group related file templates into folders and use `folder_template` or the `template` property to insert them all at once
- **Binary files** - Add logos, PDFs, or other assets to file templates; they'll be copied without modification
- **Preview before generating** - Use the Preview panel to see exactly what will be created
- **Generate single files** - Right-click a file template and select "Generate this file" to create it standalone
- **Generate entire folders** - Right-click a folder in File Templates and select "Generate this folder" to create all files in that folder
- **Apply to all conflicts** - When generating into an existing folder, check "Apply to all" to handle all conflicts the same way
- **Python for dynamic content** - Use Python blocks to generate repetitive structures or computed content
- **Case-insensitive tokens** - `{mp:title}`, `{MP:TITLE}`, and `{Mp:Title}` all work the same

## Contributing

Issues and feature requests: https://github.com/anthropics/makeproject/issues
