# File formats
### Author: Lukas (Viridis) Dubsik

The application reads and writes UTF-8 JSON. The current version of the format is `1.0`. It only describes the data of the GUI, the IRCOMP specification will be a separate thing. The schema is in [exchange.schema.json](exchange.schema.json).

## Request files
A request has the study ID, the request ID, one revision and the labels of its targets. The revision says the reference, the profile, the coordinate system and the intervals. A request file can be opened as a new study, but only if it isn't saved already - an import never overwrites a saved study.

## Evidence files
Evidence has a request ID, the whole revision it was made for, information about the tool that produced it, and the candidates. Both the request ID and the revision have to match the study it is imported into. Candidate IDs are only unique inside one file. The scores keep their model, scale, direction and availability as the tool sent them. 0 is a real value, a missing score is shown as missing.

The original bytes of the evidence file are kept along with their SHA-256 checksum. The decisions are stored separately, so writing a reason can't change the imported data. A different file with an already used bundle ID is refused.

## Review packages
A review package has the saved request, the chosen collections and the original evidence files their candidates (and supporting candidates) come from. It also says how many decisions are unfinished - a decision is unfinished when it is undecided, needs clarification or has no reason, and an empty collection counts as one unfinished item too. While anything is unfinished, the package is a draft. A finished review only means every candidate has a decision with a reason, not that the decisions are right.

## Examples and references
The [examples](examples/) directory has a request and three evidence files: one matching it, one empty and one that doesn't match. All the candidates are made up. The mismatching one is there on purpose, to show the import error. An empty list of candidates is valid.

[catalogue.json](catalogue.json) lists the supported references and profiles. The GRCh38.p14 entry only has the 24 nuclear chromosomes, their accessions and lengths are taken from the [NCBI report](references/grch38-p14-assembly-report.txt) kept here. The mitochondrion, patches and alternative loci are left out. The report's calendar metadata is omitted from the retained copy. The catalogue contains the source URL and the hash of this local copy. Knowing the lengths doesn't mean the FASTA file is there or correct.

The checks done at runtime are described in [implementation details](../docs/architecture.md). The [IRCOMP integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897) have the future specification fields and the checks of the conversion.

## Updating the format
The data are only defined once, in the Python models. `scripts/generate_contracts.py` writes the other files from them, so after changing a model run `make contracts` and commit the generated files together with the change:

| Generated file | Made from |
|-|-|
| `contracts/exchange.schema.json` | Request, evidence and review models in `domain/models.py` |
| `web/src/shared/types.generated.ts` | Domain models, commands and the response models in `application/responses.py` |
| `web/src/shared/constants.generated.ts` | The `MAX_*` values in `domain/constants.py` |

Never edit the generated files by hand, `make check` regenerates them in memory and fails if the committed ones differ (it doesn't overwrite them). The generator needs both the Python and the web dependencies, as it formats the TypeScript with Prettier.

A few rules only apply to the files, so they are added by the generator and not by the models: a request needs at least one target, a metric has a value exactly when it is present, and a review is a draft exactly when something is unfinished. Changing one of these means changing the generator (and the matching domain rule).

The format itself is still `1.0`, the field names and file kinds didn't change. The keys of the target labels have to be UUIDs. Relations the schema can't express, like evidence matching its revision, are still checked by the domain rules.
