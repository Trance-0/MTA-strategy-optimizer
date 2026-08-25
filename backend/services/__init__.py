"""Work the backend performs rather than data it reads.

The repository layer answers questions about stored data. This layer runs
things: pipeline stages as child processes, the three model endpoints, and the
settings changes that decide which source the repository reads from.
"""
