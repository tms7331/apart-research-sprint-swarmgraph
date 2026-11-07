"""The data sources: each fills a ledger with one experiment's or result's numbers, tables, figures and texts.

A source is a function of a `Ledger`, registered under a name with `@source`. The build runs the sources of
every module in this package, each into a ledger of its own, and merges them, so two sources can't claim one
key."""

import importlib
import pkgutil
from collections.abc import Callable

from paper.ledger import Ledger

Source = Callable[[Ledger], None]

SOURCES: dict[str, Source] = {}


def source(name: str) -> Callable[[Source], Source]:
    """Registers a data source under `name`."""

    def register(function: Source) -> Source:
        if SOURCES.get(name, function) is not function:
            raise ValueError(f"two data sources are named {name}")
        SOURCES[name] = function
        return function

    return register


def registered() -> dict[str, Source]:
    """Every source in this package's modules, by name."""
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
    return dict(SOURCES)
