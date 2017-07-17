import logging
import sys


LOGGER = logging.getLogger('alpakka')

HANDLER = logging.StreamHandler(sys.stderr)
LOGGER.addHandler(HANDLER)

HANDLER.formatter = FORMATTER = logging.Formatter(
    "alpakka[%(levelname)s]: %(message)s")
