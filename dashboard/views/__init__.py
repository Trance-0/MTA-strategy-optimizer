"""The six dashboard views, mirroring the reference design's navigation.

Each module exposes a single `render()` that draws one full page and takes no
arguments. Views read only through `dashboard.data_source` and never compute
an attribution or budget figure themselves: the pipeline owns those numbers,
and a view that recomputed one would become a second, divergent implementation.

    Command Center      the headline state of the account
    Budget Manager      the recommended allocation and how it was derived
    Campaigns           historical performance, filterable and queryable
    Campaign Optimizer  what the optimised outcome would be, per Campaign
    Optimization Log    the run record and its provenance
    Knowledge Base      the vocabulary and rules the numbers obey
"""
