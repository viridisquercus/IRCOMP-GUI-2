# AI contribution audit

### Name: Lukas (Viridis) Dubsik

## Earlier reported use

The Cypress tests were reported as AI-generated from the author's Cucumber
scenario descriptions. This is a record of that reported work, not a complete
authorship history of the project.

## Shared definitions and API responses

The model/schema synchronization, typed API responses and response-validation
changes were implemented with OpenAI Codex assistance. This includes the new
generator, response models, client response checker and focused tests.

The exchange schema and browser files marked as generated are produced by
`scripts/generate_contracts.py` from the Python models. They are ordinary script
output; their generated status does not establish the authorship of the source
models. Existing code outside these changes was not re-audited for authorship.
