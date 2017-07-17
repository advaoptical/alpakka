__all__ = ['NodeWrapper', 'wrap_module']

import alpakka

from .nodewrapper import NodeWrapper


def wrap_module(statement, wool=None):
    """
    Wrap the module statement for akka code generation.

    :param statement: the module statement
    :return:          the wrapped module representation
    """
    if wool is None:
        wool = alpakka.WOOLS.default
    return wool['module'](statement)
