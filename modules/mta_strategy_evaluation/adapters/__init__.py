"""Adapters bridging externally contributed models into this pipeline.

One module per contributed model. An adapter is project code and follows
every project rule; the ``contrib/`` folder it adapts follows none of them,
because that folder is the contributor's own record and is preserved
verbatim.

Every adapter owes four things, specified in
``docs/en/strategy-evaluation/contributed-models/index.md``: it translates
grain onto the canonical Campaign x marketplace x period, it checks feature
admissibility against ``FORBIDDEN_RESPONSE_FEATURES``, it imports the
contributed code rather than copying it, and it reports the model's measured
quality alongside its predictions.
"""
