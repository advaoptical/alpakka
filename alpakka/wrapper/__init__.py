from .nodewrapper import Module


def wrap_module(statement):
    """
    Wrap the module statement for akka code generation.

    :param statement: the module statement
    :return: the wrapped module representation
    """
    return Module(statement)
