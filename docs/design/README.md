# Interface design

The interface uses three views over one study. Prepare edits targets and their
reference context. Review places imported evidence beside the decision editor.
Export shows what will be included in the downloaded file.

## Wireframes

| File | Purpose |
| --- | --- |
| [Prepare](wireframes/01-prepare.svg) | Target list, interval editor and checks |
| [Prepare error](wireframes/02-prepare-error.svg) | Invalid input and field correction |
| [Review](wireframes/03-review.svg) | Source evidence and the separate decision editor |
| [Import mismatch](wireframes/04-import-mismatch.svg) | Expected and received request context |
| [Export](wireframes/05-export.svg) | Saved request, decisions and unfinished work |

These files show the initial design, not captures of the running application.
The examples are synthetic. SVG files can be edited directly in a text or vector
editor.

Editable [navigation](diagrams/navigation.svg) and
[architecture](diagrams/architecture.svg) diagrams describe the data flow.

## Working with input

The study context and save status remain visible between views. Editing is done
inside the page. An error names the problem and the relevant input; status colours
also have text. On a narrow screen, the panels are placed below each other.

Typed text is kept apart from accepted values, so an unfinished interval does not
replace a valid target. Historical evidence keeps its request revision. Scores
from different sources are not combined into one score.

The [interview plan](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29425665)
covers interval entry, candidate decisions and collections.
Engineering checks alone do not establish usability. The data flow is described
in [implementation details](../architecture.md).
