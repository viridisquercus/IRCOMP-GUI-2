# ************************************************************************
# @file constants.py
# @brief Limits and fixed values used through the whole application
# @author Lukas (Viridis) Dubsik
# @version 0.1
#
# Detailed description:
#  All the limits are kept here so the models, rules and API all use the
#  same numbers. Changing a value here changes it everywhere.
# ************************************************************************

"""Hold the limits and fixed values used through the application."""

# Sizes of the files
MAX_FILE = 1024 * 1024  # Max size of one imported file - 1 MiB
MAX_BASE64 = 4 * ((MAX_FILE + 2) // 3)  # Max length of MAX_FILE encoded in base64
MAX_DOCUMENT = 20 * 1024 * 1024  # Max size of stored or exported document - 20 MiB
MAX_BODY = 2 * 1024 * 1024  # Max size of one HTTP body - 2 MiB
MAX_DEPTH = 32  # Max nesting of objects and lists in JSON
MAX_SAFE_INTEGER = 9007199254740991  # Biggest integer the browser holds exactly

# Limits of the study
MAX_TARGETS = 50  # Targets in one revision
MAX_REVISIONS = 200  # Revisions retained in one study
MAX_BUNDLES = 10  # Evidence bundles attached to one study
MAX_COLLECTIONS = 20  # Review collections in one study
MAX_MEMBERSHIPS = 1000  # Memberships across all collections of one study
MAX_CANDIDATES = 200  # Candidates in one evidence bundle
MAX_METRICS = 20  # Metrics of one candidate
MAX_REFERENCES = 100  # Supporting evidence references of one decision
MAX_DEPENDENCIES = 100  # External dependencies declared by one bundle
MAX_LABEL = 200  # Length of labels, titles and names
MAX_RATIONALE = 4000  # Length of a decision rationale

# Limits of the in-memory buffers
MAX_PREVIEWS = 5  # Import previews kept until confirmed or cancelled
MAX_EXPORTS = 5  # Prepared downloads, the oldest one is dropped first

# Values used for a newly created study
DEMO_REFERENCE = "demo-reference-v1"
DEMO_PROFILE = "demo-spcas9-ngg-v1"
