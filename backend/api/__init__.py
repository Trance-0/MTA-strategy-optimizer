"""The HTTP surface: one blueprint per family of routes.

Each blueprint translates between HTTP and the layer beneath it and does
nothing else -- no SQL, no file reads, no model mathematics. A route decides
the status code, names the remedy in the message, and delegates.
"""
