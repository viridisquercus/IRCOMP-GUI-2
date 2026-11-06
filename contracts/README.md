# File formats

The application reads and writes UTF-8 JSON. The current local format version is
`1.0`; it describes GUI data and is separate from the future IRCOMP specification.
The schema is [exchange.schema.json](exchange.schema.json).

## Request files

A request contains the study ID, request ID, one revision and its target labels.
The revision gives the reference, profile, coordinate convention and intervals.
This file can be opened as a new working study if its identity is not already
saved. Import does not overwrite an existing saved study.

## Evidence files

Evidence contains a request ID, complete revision context, source information and
candidates. Both the request ID and the revision must match the selected context.
Candidates use IDs inside their bundle. Scores keep the source's model, scale,
direction and availability information. Zero remains a supplied value; missing
information is displayed separately.

The original evidence bytes are kept with a SHA-256 checksum. Review decisions
are stored separately, so editing a reason cannot change imported observations.
The same bundle ID with different bytes is refused.

## Review packages

A review package contains the saved request, selected collections and the original
evidence files needed by their candidates and supporting references. The package
also states how many decisions remain unfinished. It is a draft while a decision
is undecided, needs clarification or has no reason. A completed review describes
finished bookkeeping; it does not verify a scientific conclusion.

## Examples and references

The [examples](examples/) directory contains a request and compatible, empty and
mismatching evidence. All candidate data is synthetic. The mismatch is deliberate
so that the import error can be demonstrated; an empty candidate list is valid.

[catalogue.json](catalogue.json) lists the supported references and profiles.
The GRCh38.p14 entry contains only 24 nuclear chromosomes. Accession identifiers
and lengths come from the retained [NCBI report](references/grch38-p14-assembly-report.txt).
Mitochondria, patches and alternative loci are excluded. The source URL and hash
are stored in the catalogue. These lengths do not establish that a FASTA file is
available or correct.

Runtime checks are described in [implementation details](../docs/architecture.md).
The [IRCOMP integration notes](https://viridisquercusnova.atlassian.net/wiki/spaces/IRCOMP/pages/29392897)
record the future specification fields and conversion checks.
