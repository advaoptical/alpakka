import logging

formatter = logging.Formatter("alpakka [%(module)s, %(levelname)s]: "
                              "%(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)

LOGGER = logging.getLogger('alpakka')
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(handler)
