__all__ = ('NodeWrapper', 'wrap_module', 'Grouponder', 'Typonder')

import alpakka

from .nodewrapper import NodeWrapper
from .grouponder import Grouponder
from .typonder import Typonder


def wrap_module(statement, wool=None):
    """
    Wrap the module statement for akka code generation.

    :param statement: the module statement
    :return:          the wrapped module representation
    """
    if wool is None:
        wool = alpakka.WOOLS.default
    return wool['module'](statement)
