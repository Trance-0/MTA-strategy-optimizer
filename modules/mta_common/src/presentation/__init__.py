"""Presentation-only types, isolated from the core canonical data model.

Nothing under ``modules/mta_common/src/presentation/`` may be imported by
``modules/mta_common/src/`` itself, and no class in that parent package
accepts a type from this package as a field. This package exists for values
that exist purely to be displayed (for example, in the dashboard), never to
be read by an attribution model, a strategy recommender, or a future
optimizer.
"""
