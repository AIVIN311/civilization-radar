from src.series_registry import resolve_series


def resolve(domain, series_raw):
    return resolve_series(series_raw, domain)
