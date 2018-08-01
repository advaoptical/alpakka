from argparse import ArgumentParser

import alpakka


PARSER = ArgumentParser('alpakka')


def command(func):
    """
    Decorator for registering `func` as alpakka command, which be invoked from
    the command line like::

       alpakka --func-name

    Whereby underscores in the function name are turned into hyphens

    Every command function must return an alpakka exit code number
    """
    PARSER.add_argument(
        '--' + func.__name__.replace('_', '-'), dest='command',
        action='store_const', const=func, default=None,
        help=func.__doc__)
    return func


@command
def list_wools():
    """
    List all registered Wools for knitting code
    FIXME: Does not work, missing ID
    """
    for name, wool in alpakka.WOOLS.items():
        print("[{}] {!r}".format(name, wool))
    return 0
