"""Configure logging for the application."""
import logging
import logging.handlers
import sys

def setup_logging() -> None:
    """Configure stdout logging and (if available) systemd journal."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Clear any existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Stdout handler with concise format
    stdout_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # Try systemd journal if available
    try:
        import systemd.journal  # type: ignore
        journal_handler = systemd.journal.JournalHandler()
        journal_handler.setLevel(logging.INFO)
        root.addHandler(journal_handler)
    except Exception:
        # systemd.journal not available – that's fine
        pass
