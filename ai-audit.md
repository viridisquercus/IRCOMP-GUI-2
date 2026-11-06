# AI contribution audit

### Name: Lukas (Viridis) Dubsik

## Scope

AI contributed substantially to parts of the code while having no effect on most others. The main area where AI was used was during testing creation - where the testing files in cypress were fully ai generated, with me only providing the cucumber description and AI doing the rest.


## Shared definitions and API responses

The model/schema synchronization, typed API responses and response-validation
changes were implemented with OpenAI Codex assistance. This includes the new
generator, response models, client response checker and focused tests.

The exchange schema and browser files marked as generated are produced by
`scripts/generate_contracts.py` from the Python models. They are ordinary script
output; their generated status does not establish the authorship of the source
models. Existing code outside these changes was not re-audited for authorship.
