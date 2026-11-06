# File formats
### Author: Lukas (Viridis) Dubsik
#### Date: 6.11.2026

The application reads and writes UTF-8 JSON. The current version of the format is `1.0`. It only describes the data of the GUI, the IRCOMP specification will be a separate thing. The schema is in [exchange.schema.json](exchange.schema.json).

## Request files
A request has the study ID, the request ID, one revision and the labels of its targets. The revision says the reference, the profile, the coordinate system and the intervals. A request file can be opened as a new study, but only if it isn't saved already - an import never overwrites a saved study.

## Evidence files
Evidence has a request ID, the whole revision it was made for, information about the tool that produced it, and the candidates. Both the request ID and the revision have to match the study it is imported into. Candidate IDs are only unique inside one file. The scores keep their model, scale, direction and availability as the tool sent them. 0 is a real value, a missing score is shown as missing.

The original bytes of the evidence file are kept along with their SHA-256 checksum. The decisions are stored separately, so writing a reason can't change the imported data. A different file with an already used bundle ID is refused.

## Review packages
A review package has the saved request, the chosen collections and the original evidence files their candidates (and supporting candidates) come from. It also says how many decisions are unfinished. A decision is unfinished if it is undecided, needs clarification or has no reason. An empty selected collection also counts as one unfinished item. The package stays a draft while any such item remains. A finished review means every member of the selected collections has a completed decision with a reason, not that the decisions are right.

## Examples and references
The [examples](examples/) directory has a request and three evidence files: one matching it, one empty and one that doesn't match. All the candidates are made up. The mismatching one is there on purpose, to show the import error. An empty list of candidates is valid.

[catalogue.json](catalogue.json) lists the supported references and profiles. The GRCh38.p14 entry only has the 24 nuclear chromosomes, their accessions and lengths are taken from the [NCBI report](references/grch38-p14-assembly-report.txt) kept here. The mitochondrion, patches and alternative loci are left out. The URL and hash of the report are in the catalogue. Knowing the lengths doesn't mean the FASTA file is there or correct.

The checks done at runtime are described in [implementation details](../docs/architecture.md). The [IRCOMP integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897) have the future specification fields and the checks of the conversion.

## Updating the format

The Python models are the source of the data definitions. After changing them,
run `make contracts` and commit the generated files with the source change.

| Generated file | Source |
| --- | --- |
| `contracts/exchange.schema.json` | Request, evidence and review models in `src/ircomp_gui/domain/models.py`, plus the file-only conditions in the generator |
| `web/src/shared/types.generated.ts` | Domain models, application commands and response models |
| `web/src/shared/schemas.generated.ts` | Serialized API response models and their referenced definitions |
| `web/src/shared/constants.generated.ts` | Values starting with `MAX_` in `src/ircomp_gui/domain/constants.py` |

The generator is `scripts/generate_contracts.py`. It also supplies conditions
specific to exchange files: a request needs at least one target, metric
availability must agree with its value, and review status must agree with the
unfinished count. Changes to those conditions need a generator change as well
as any corresponding domain-rule change.

`make contracts` requires the Python dependencies and the web dependencies,
including Prettier. `make check` computes the generated output and compares it
with the committed files; it does not rewrite them. Edit the sources rather
than the generated files. `web/src/shared/types.ts` keeps the import names used
by the views, and `constants.ts` re-exports generated limits alongside the
browser-only settings.

Browser response models are in `src/ircomp_gui/application/responses.py`.
They describe HTTP data, not the exchange files. In particular, `StudyView`
does not include original evidence bytes, and each collection view adds a
backend-calculated `unresolved_count`. Import summaries include `null` for
unavailable fields. Update the client and backend together.

The exchange format is still `1.0`; its field names and file kinds are unchanged.
The generated schema uses model names in `$defs`, explicit lowercase UUID
patterns and `anyOf` for the three kinds. Their distinct `kind` values prevent
overlap. Default-value annotations do not make required file fields optional.
Every target-label key must match the UUID pattern and every label must meet
the string constraints. Domain checks still enforce relationships that the
schema does not express, such as evidence matching the retained revision.

These files are generated by a Python script. The AI assistance used to
implement the generator and API changes is recorded separately in
[the contribution audit](../ai-audit.md); generation does not establish who
wrote the source models.
