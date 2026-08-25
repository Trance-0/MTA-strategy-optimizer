"""Package root for the strategy evaluation layer.

Holds the canonical strategy decision type, the three assurance layers that
score one, and the adapters that bridge externally contributed response
models into this pipeline. See ``docs/en/strategy-evaluation/`` for the
specification these modules implement.

``contrib/`` deliberately has no ``__init__.py``: the folders under it are
preserved byte-for-byte as their contributors produced them, and adding a
package marker inside one would be an edit. Adapters reach that code through
``importlib`` instead.
"""
