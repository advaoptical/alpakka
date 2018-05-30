import logging
import re
import sys
from collections import OrderedDict

import alpakka
from alpakka.wools import Wool
from alpakka.templates import template_var, create_context

WOOLS = alpakka.WOOLS

# configuration for logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

TYPE_PATTERNS = OrderedDict([
    ('binary', 'binary'),
    ('bits', 'bits'),
    ('boolean', 'boolean'),
    ('decimal64', 'decimal64'),
    ('empty', 'empty'),
    ('enumeration', 'enumeration'),
    ('identityref', 'identityref'),
    ('instance-identifier', 'instance-identifier'),
    ('int8', 'int8'),
    ('int16', 'int16'),
    ('int32', 'int32'),
    ('int64', 'int64'),
    ('leafref', 'leafref'),
    ('string', 'string'),
    ('uint8', 'uint8'),
    ('uint16', 'uint16'),
    ('uint32', 'uint32'),
    ('uint64', 'uint64'),
    ('union', 'union')
])


class NodeWrapperMeta(type):
    """
    Metaclass for :class:`NodeWrapper`

    Allows to add the YANG node name to the definition of a derived class,
    which automagically registers that class in its Wool.

    See :class:`NodeWrapper` for usage examples
    """

    def __new__(mcs, clsname, bases, clsattrs, *args, yang=None):
        return type.__new__(mcs, clsname, bases, clsattrs, *args)

    def __init__(cls, clsname, bases, clsattrs, *args, yang=None):
        type.__init__(cls, clsname, bases, clsattrs, *args)

        # To get registered, the class must NOT be defined in sub-packages
        # (sub-directories) of this basic wrapper package or a wool package.
        # Only classes from sub-modules (.py files) are allowed
        pkgname = sys.modules[cls.__module__].__package__
        if pkgname == sys.modules[__name__].__package__:
            wool = getattr(WOOLS, 'default', None)
            if wool is None:
                wool = WOOLS.default = Wool('default', __name__)
        elif pkgname in WOOLS:
            wool = WOOLS[pkgname]
        else:
            return

        # Give every class reference to its Wools for easy access
        cls.WOOL = wool

        wrapdict = wool._yang_wrappers

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
    <class 'alpakka.wrapper.nodewrapper.SomeNode'>
    """
    prefix = ""

    def __init__(self, statement, parent):
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

    @property
    def template_context(self):
        return create_context(self)

    @template_var
    def yang_name(self):
        return self.statement.arg

    @template_var
    def yang_type(self):
        return self.statement.keyword

    @template_var
    def yang_module(self):
        return (self.statement.top or self.statement).i_modulename

    @template_var
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
        # Key generation for elements which could be imported from other Modules
        # or be implemented locally
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