import sys
from collections import OrderedDict

import alpakka
from alpakka.wools import Wool

WOOLS = alpakka.WOOLS


class NodeWrapperMeta(type):
    """
    Metaclass for :class:`NodeWrapper`

    Allows to add the YANG node name to the definition of a derived class,
    which automagically registers that class in its Wool.

    See :class:`NodeWrapper` for usage examples
    """

    mixins = {}

    def __new__(mcs, clsname, bases, clsattrs, *args, yang=None):
        # To support @NodeWrapper.mixin classes in bases, we need a new
        # metaclass additionally derived from all the metaclasses of the
        # bases, but w/o duplicates or metaclasses that are superclasses of
        # others in the list of base metaclasses
        metabases = [mcs]
        for meta in map(type, bases):
            metabases = [mb for mb in metabases if not issubclass(meta, mb)]
            if meta not in metabases:
                metabases.append(meta)

        class Meta(*metabases):
            mixins = {}

        return type.__new__(Meta, clsname, bases, clsattrs, *args)

    def __init__(cls, clsname, bases, clsattrs, *args, yang=None):
        type.__init__(cls, clsname, bases, clsattrs, *args)

        module = sys.modules.get(cls.__module__)
        if module is None:
            return

        # To get registered, the class must NOT be defined in sub-packages
        # (sub-directories) of this basic wrapper package or a wool package.
        # Only classes from sub-modules (.py files) are allowed
        pkgname = module.__package__
        if pkgname == sys.modules[__name__].__package__:
            wool = getattr(WOOLS, 'default', None)
            if wool is None:
                wool = WOOLS.default = Wool('default', __package__)
        elif pkgname in WOOLS:
            wool = WOOLS[pkgname]
        else:
            return

        # Give every class reference to its Wools for easy access
        cls.WOOL = wool

        wrapdict = wool.yang_wrappers

        # If we have an explicit class SomeWrapper(..., yang=<yang name>)
        # relation, then just add it to the wrapper dict
        if yang:
            wrapdict[yang] = cls
            return

        # Otherwise look if any base class already exists in the wrapper dict
        # and exchange it accordingly
        wrapitems = list(wrapdict.items())
        for base in cls.mro()[1:]:
            for yangname, wrapcls in wrapitems:
                if wrapcls is base:
                    wrapdict[yangname] = cls

    def mixin(cls, mixincls):
        """
        Class decorator for defining YANG node wrapper plugins in Wools.

        Any class in the wrapper hierarchy can be extended with mixins:

        >>> @NodeWrapper.mixin
        ... class SomeMixin:
        ...     def upper_name(self):
        ...         return self.yang_name().upper()

        Mixins are stored by their Wool package name in the wrapper class'
        meta ``.mixins`` dictionary:

        >>> NodeWrapper.mixins
        {...'alpakka.wrapper': [<class '...SomeMixin'>]...}

        Accessing a wrapper class through a Wool will automagically create a
        derived class with all the applicable mixins as additional (higher
        priority) base classes

        This dynamic class creation process is cached. If there might be a
        need to clear the cache for whatever reason, you can do so with:

        >>> Wool._woolify.cache_clear()

        The new class gets a special ``.__module__`` name referring to the
        alpakka.WOOLS registry:

        >>> WOOLS.default.Module.mro()
        [<class '...WOOLS['default'].Module'>, <class '...SomeMixin'>, ...]

        And after instantiation, all additional mixin features are available:

        >>> _dummy = __import__('pyang').statements.Statement(
        ...     None, None, None, 'module', 'some-module')

        >>> wrapped_module =  WOOLS.default.Module(_dummy)
        >>> wrapped_module.yang_name()
        'some-module'
        >>> wrapped_module.upper_name()
        'SOME-MODULE'

        :return: The original `mixincls` object
        """
        pkgname = sys.modules[mixincls.__module__].__package__
        if pkgname == sys.modules[__name__].__package__ or pkgname in WOOLS:
            type(cls).mixins.setdefault(pkgname, []).append(mixincls)
        return mixincls


class NodeWrapper(metaclass=NodeWrapperMeta):
    """
    Base class for node wrappers. It includes the base setup.

    If a derived classes directly maps to a YANG node, its name can be given
    as additional keyword-only argument to the class definition:

    >>> class SomeNode(NodeWrapper, yang='some-node'):
    ...     pass

    This will automagically register that class its Wool. In this case to
    ``WOOLS.default``, since we are in the default wool package and not in a
    customized wool:

    >>> WOOLS.default['some-node']
    <class 'alpakka.WOOLS['default'].SomeNode'>
    >>> WOOLS.default['some-node'].mro()
    [..., <class 'alpakka.wrapper.nodewrapper.SomeNode'>, ...]
    """
    prefix = ""

    def __init__(self, statement, parent=None):
        """
        The Constructor for NodeWrapper object.

        Attributes which are common for all wrapped statements
        :param statement: the original statement generated from pyang
        :param parent: the wrapped parent statement of the current statement,
                None for the top element
        :param yang_stmt_type: yang type of the current statment, like module,
                container, list, leaf and so on
        :param yang_stmt_name: name of the current statement, is the same
                like in the original yang file
        :param description: string containing the description of the current
                statement provided by the yang file
        :param config: if the current statement has config substatement the
                value this one is stored in this variable
        """

        self.statement = statement
        self.parent = parent
        self.is_augmented = False
        for stmt in statement.substmts:
            if stmt.keyword == 'description' and stmt.arg.lower() != "none":
                self.description = stmt.arg
            elif stmt.keyword == 'config':
                self.config = stmt.arg.lower() == 'true'
        if self.top() is not self and self.yang_type() not in ('enum', 'input',
                                                               'output',
                                                               'type'):
            nodes = self.top().all_nodes.setdefault(statement.keyword,
                                                    OrderedDict())
            nodes[self.generate_key()] = self

    def yang_name(self):
        return self.statement.arg

    def yang_type(self):
        return self.statement.keyword

    def yang_module(self):
        return (self.statement.top or self.statement).i_modulename

    def top(self):
        """
        Find the root wrapper object by walking the tree recursively
        to the top.
        :return: the root node
        """
        if self.parent:
            return self.parent.top()
        else:
            return self

    def generate_key(self):
        """
        Generates a string which represents the path from the root element of
        the Statement to the target as uniquekey. In the case of imported
        Statements the string represents only the top element and the target
        element name

        :return: a unique key which is a human readable path to the module
        """
        key = ''
        # Key generation for elements which could be imported from other
        # Modules or be implemented locally
        if self.yang_type() == 'grouping' or self.yang_type() == 'typedef':
            return self.statement.parent.arg + "/" + self.statement.arg
        # Key generation for all other Statements
        else:
            if self.parent:
                key = self.parent.generate_key() + '/'

            return key + self.yang_name()


class Listonder():
    """
    Metaclass for all List type objects
    """

    def min_list_elements(self):
        """
        Method to return the minimum occurrence of list objects, if the
        respective substmt is present

        return: the number of minimum occurrence of list objects
        """
        for i in self.statement.search('min-elements'):
            return i.arg

    def max_list_elements(self):
        """
        Method to return the maximum occurrence of list objects, if the
        respective substmt is present

        return: the number of maximum occurrence of list objects
        """
        for i in self.statement.search('max-elements'):
            return i.arg
