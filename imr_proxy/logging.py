import logging
from rich.logging import RichHandler
def setup_logging(verbose: bool=False, quiet: bool=False, no_color: bool=False) -> None:
    level=logging.ERROR if quiet else (logging.DEBUG if verbose else logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", handlers=[RichHandler(rich_tracebacks=True, markup=not no_color)], force=True)
