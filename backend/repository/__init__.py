"""Read the dashboard's data from PostgreSQL or from the committed files.

One module per snapshot key. Each returns the same fields, types, and values
in both modes, so a view cannot tell whether `DATABASE` was true or false.
The four differences that make that non-trivial -- identifier case, flag
strings, date representation, and numeric text -- are normalised in
`coercion.py` rather than in any view.
"""
