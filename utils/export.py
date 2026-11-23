"""Helpers for the downloadable reports."""

# A spreadsheet treats a cell that starts with one of these as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _neutralise(value):
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def csv_safe(df):
    """Copy of `df` whose text cells cannot be run as formulas when the CSV is opened.

    App names and other labels come from the audited tenant. One that starts
    with "=", "+", "-" or "@" would otherwise execute in Excel or Sheets.
    """
    return df.apply(lambda column: column.map(_neutralise))
