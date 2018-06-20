from inspect import getmembers

__all__ = ['template_var', 'create_context']


def template_var(func):
    """
    Decorater for marking :class:`alpakka.wrapper.nodewrapper.NodeWrapper`
    method `func` as template variable.

    :func:`create_context` uses those methods to create a template context
    ``dict`` from a wrapped node instance.
    """
    func._is_template_var = True
    return func


def create_context(node):
    """
    Creates a template context ``dict`` from all methods of given
    class:`alpakka.wrapper.nodewrapper.NodeWrapper` instance that are
    decorated with :func:`template_var`.
    """

    return {name: member(node) for name, member in getmembers(type(node))
            if getattr(member, '_is_template_var', False)}
