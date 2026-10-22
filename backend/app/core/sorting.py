"""
Task 10 — safe resolution of a list endpoint's ``sort`` query parameter.

Every repository's ``_apply_sort`` used ``getattr(Model, name, default)``
on the raw query value, so any attribute name was accepted: a relationship
or a dunder (``?sort=__class__``) raised a 500 on public endpoints such as
GET /lessons, and an admin list could be ordered by ``password_hash``.

Only real mapped column attributes are sortable here, minus credential
columns; anything else silently falls back to the endpoint's default
column — the same outcome an unknown field always had.
"""
from sqlalchemy import inspect

NON_SORTABLE_COLUMNS = frozenset({"password_hash"})


def sortable_column(model, field_name: str, default):
    columns = {attr.key for attr in inspect(model).column_attrs}
    if field_name in columns and field_name not in NON_SORTABLE_COLUMNS:
        return getattr(model, field_name)
    return default
