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
A review package has the saved request, the chosen collections and the original evidence files their candidates (and supporting candidates) come from. It also says how many decisions are unfinished. While a decision is undecided, needs clarification or has no reason, the package is a draft. A finished review only means every candidate has a decision with a reason, not that the decisions are right.

## Examples and references
The [examples](examples/) directory has a request and three evidence files: one matching it, one empty and one that doesn't match. All the candidates are made up. The mismatching one is there on purpose, to show the import error. An empty list of candidates is valid.

[catalogue.json](catalogue.json) lists the supported references and profiles. The GRCh38.p14 entry only has the 24 nuclear chromosomes, their accessions and lengths are taken from the [NCBI report](references/grch38-p14-assembly-report.txt) kept here. The mitochondrion, patches and alternative loci are left out. The URL and hash of the report are in the catalogue. Knowing the lengths doesn't mean the FASTA file is there or correct.

The checks done at runtime are described in [implementation details](../docs/architecture.md). The [IRCOMP integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897) have the future specification fields and the checks of the conversion.

## Updating the format

The schema is generated from the Python models. Change the models first, then
run `make contracts`. The same command updates the browser types, response
schemas and constants. Do not edit these generated files by hand; `make check`
reports when they no longer match their source.

Request and evidence data are defined in `domain/models.py`. Browser responses
are defined separately in `application/responses.py`, since the browser does not
receive the original evidence bytes. The source paths are relative to
`src/ircomp_gui`. AI assistance used for this tooling is recorded in
[the contribution audit](../ai-audit.md).
