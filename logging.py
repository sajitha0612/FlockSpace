import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Passwords, tokens, API keys, chat contents and document text are never passed to this logger.
log = logging.getLogger("flockspace")
