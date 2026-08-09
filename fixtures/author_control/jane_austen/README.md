# Jane Austen public-domain control

This fixture is the non-commercial control corpus for the author
back-translation harness.

- Profiling: *Pride and Prejudice*, *Emma*, *Sense and Sensibility*
- Calibration: *Mansfield Park*
- Untouched holdout: *Persuasion*

The text files are official Project Gutenberg UTF-8 plain-text editions. The
holdout is declared in the manifest and may be existence/hash audited, but the
compiler rejects it as a prompt, retrieval, profile, or tuning source.

The derived author profile stores locations and hashes, not source passages.
Its transformation map applies reusable mechanisms to the Juicy Chastity
creative profile without importing Austen plots, characters, worldview, or
wording.
