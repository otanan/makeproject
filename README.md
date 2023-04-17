<!-- Filename:      README.md -->
<!-- Author:        Jonathan Delgado -->
<!-- Description:   GitHub README -->

<!-- Header -->
<h2 align="center">MakeProject</h2>
  <p align="center">
    Project template generator using structure definitions provided as .yaml files. Copies existing templates and populates content with provided information.
    <br />
    <br />
    Status: <em>in progress</em>
    <!-- Notion Roadmap link -->
    ·<a href="https://otanan.notion.site/Makeproject-937308a8242249a8addcad8210ad45d1"><strong>
        Notion Roadmap »
    </strong></a>
  </p>
</div>


<!-- Project Demo -->
https://user-images.githubusercontent.com/6320907/232583543-fdc9dc64-0dec-4ff7-bf5d-168ef3cbf85e.mov



<!-- ## Table of contents
* [Contact](#contact)
* [Acknowledgments](#acknowledgments) -->


<!-- ## Installation

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

1. First step
2. Clone the repo
   ```sh
   git clone https://github.com/github_username/repo_name.git
   ```
3. Import the package
   ```python
   import ytlink
   ```


<p align="right">(<a href="#readme-top">back to top</a>)</p> -->

## Usage
### Creating Project Structures
A project structure is a .yaml file whose contents reflect the layout of the directory as well as any files whose contents will be generated from a template, e.g.
 ```yaml
# Generate quizzes to assess students.
- assessments:

  - $teaching-preamble.sty: teaching.sty

  - quiz_01:
    - $teaching-quiz.tex: quiz_01.tex

  - quiz_02:
    - $teaching-quiz.tex: quiz_02.tex

  - quiz_03:
    - $teaching-quiz.tex: quiz_03.tex
```
The top-level comment will be used as a description when choosing project structures.

The `$` key indicates that this file's contents comes from a template. It will search the templates folder for the template `quiz.tex` in the `teaching` folder (indicated by the `-` separator as belonging to the `teaching` folder. It will populate the contents and rename the file to `quiz_01.tex` etc.




### Generating Projects
Type `makeproject` into the terminal to run the script. Choose from existing project structures to generate the project.



<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

Refer to the [Notion Roadmap] for future features and the state of the project.


<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact
Created by [Jonathan Delgado](https://jdelgado.net/).


<p align="right">(<a href="#readme-top">back to top</a>)</p>

[Notion Roadmap]: https://otanan.notion.site/Makeproject-937308a8242249a8addcad8210ad45d1
