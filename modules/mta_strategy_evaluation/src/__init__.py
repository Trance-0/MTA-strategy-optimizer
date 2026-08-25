"""Implementation package for the strategy evaluation layer.

``strategy_output.py`` defines the decision every strategy returns and the
conservation contract it is checked against. ``strategy_projection.py`` reads
the two committed strategy artifacts into that type.
``evaluation_episode.py`` pairs a decision with the observations that
followed it and runs the three assurance layers over the pair.

Standard library only, plus ``modules/mta_common/``. Nothing here imports a
concrete strategy, so the recommendation module keeps producing its own
artifacts without knowing an evaluation layer exists.
"""
