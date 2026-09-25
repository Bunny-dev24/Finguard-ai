import logging, sys

def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("finguard")
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger

logger = setup_logging()