# Interface design
### Author: Lukas (Viridis) Dubsik

The interface has three views over one study. Prepare edits the targets and their reference, Review puts the imported evidence next to the editor of the decision, and Export shows what will be in the downloaded file.

## Wireframes

| File | What it shows |
|-|-|
| [Prepare](wireframes/01-prepare.svg) | Target list, interval editor and checks |
| [Prepare error](wireframes/02-prepare-error.svg) | Wrong input and how the field is pointed out |
| [Review](wireframes/03-review.svg) | The evidence and the decision editor next to it |
| [Import mismatch](wireframes/04-import-mismatch.svg) | Expected and received request of an evidence file |
| [Export](wireframes/05-export.svg) | Saved request, decisions and what is still unfinished |

These are the first drafts of the design, not screenshots of the finished application (some texts changed since). The data in them are made up. The SVGs can be edited in any text or vector editor.

The [navigation](diagrams/navigation.svg) and [architecture](diagrams/architecture.svg) diagrams show how the data go through the application.

## Working with the input

The study, its revision and whether it is saved stay visible in every view. Everything is edited directly in the page. An error says what is wrong and in which field, and the colours of the states always come with a text too (so they work without colours as well). On a narrow screen the panels go under each other.

What you type is kept apart from the applied values, so an unfinished interval never replaces a valid target. Older evidence keeps its revision, and scores from different tools are never merged into one.
