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


class Typonder(NodeWrapper):
    """
    Base class for node wrappers that have a type property.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a typonder which extracts the data-type.

        :param data_type:
            string containing the argument of the type attribute of the yang
            statement
        :param is_build_in_type:
            boolean indicating is the data_type a yang base type or a typedef
            type
        :param enumeration:
            attribute containing the enumeration object if the data_type is
            enumeration
        :param union:
            attribute containing the union object if the data_type is union
        """
        super().__init__(statement, parent)
        type_stmt = statement.search_one('type')
        if type_stmt:
            # processing if the yang type is a base type
            if type_stmt.arg in TYPE_PATTERNS:
                # check whether the data_type is defined by the wool as
                # language specific type
                data_type_paterns = self.WOOL._data_type_patterns.items()
                for pattern, wool_type_name in data_type_paterns:
                    if re.match(pattern, type_stmt.arg):
                        self.data_type = wool_type_name
                        break
                else:
                    # additional compliance test that the type is a correct
                    # Yang type
                    self.data_type = TYPE_PATTERNS[type_stmt.arg]
                self.is_build_in_type = True
            # processing if the yang type is typedef
            else:
                self.data_type = type_stmt.arg
                # check is the typedef already generated
                if self.data_type not in self.top().derived_types.keys():
                    self.top().derived_types[self.data_type] = (
                        self.WOOL['typedef'](type_stmt.i_typedef,
                                             parent=self.top()))
                self.is_build_in_type = False

            # special processing if the data_type is enumeration
            if self.data_type == 'enumeration':
                self.enumeration = Enumeration(type_stmt, parent=self)
            # special processing if the data_type is an union
            elif self.data_type == 'union':
                self.union = Union(type_stmt, parent=self)
            elif self.data_type == 'leafref':
                if hasattr(type_stmt.i_type_spec, 'i_target_node'):
                    self.reference = self.WOOL['leaf'](
                        type_stmt.i_type_spec.i_target_node, self)
                self.path = next(
                    (i.substmts[0].arg for i in statement.substmts if
                     i.keyword == 'type'), None)

    @template_var
    def default_value(self):
        """
        Methode that returns the default value of a node if present

        :return: default value as string
        """
        for item in self.statement.search('default'):
            return item.arg

    @template_var
    def is_mandatory(self):
        """
        Methodes that returns the True if the node was selected to be
        mandatory and False if it is not mandatory
        :return:
        """
        for item in self.statement.search('mandatory'):
            return item.arg == 'true'

        return False


class Grouponder(NodeWrapper):
    """
    Base class for node wrappers that group variables.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a grouponder which extracts all statements which are
        childes of the current statement

        :param children: all wrapped statements which are children of this
                         statement as list
        :param uses: if the current statement has a uses substmt a Grouping
                     object created and stored in the uses var
        """
        super().__init__(statement, parent)
        self.uses = OrderedDict()
        self.children = OrderedDict()

        # the following line separates stmts which are imported with 'uses'
        # from normal integrated stmts
        children_list = set(getattr(statement, 'i_children', ()))

        # wrap all children of the node
        for child in children_list:
            child_wrapper = self.WOOL.get(child.keyword)
            if child_wrapper:
                self.children[child.arg] = child_wrapper(child, parent=self)
            else:
                logging.debug("No wrapper for yang type: %s (%s)" %
                              (child.keyword, child.arg))

        # find all stmts which are imported with a 'uses' substmt and wrap the
        # Grouping object related to ths uses
        uses_list = set(statement.search('uses'))
        for stmt in uses_list:
            # check is the used grouping already wrapped
            # if so, the wrapped grouping is linked in the 'uses' variable
            # if not a the grouping statement is wrapped
            key = stmt.i_grouping.parent.arg + '/' + stmt.i_grouping.arg
            group = self.top().all_nodes.get('grouping', {}).get(key)
            if group:
                self.uses[group.yang_name()] = group
            else:
                self.uses[stmt.i_grouping.arg] = \
                    self.WOOL['grouping'](stmt.i_grouping, parent=self.top())

        # special handling for augment imports
        # collect all keys of augments

        augmented_keys = []

        for child in set(getattr(statement, 'i_children', ())):
            if hasattr(child, 'i_augment'):
                self.is_augmented = True
                statement = child.i_augment
                if statement.parent.arg not in augmented_keys:
                    augmented_keys.append(statement.parent.arg)
                    # Handling for Groupings which are imported with
                    # a augment statement
                    for stmt in set(statement.search('uses')):
                        key = stmt.i_grouping.parent.arg + '/' + \
                              stmt.i_grouping.arg
                        group = self.top().all_nodes.get('grouping', {}).get(
                            key)
                        if group:
                            self.uses[group.yang_name()] = group
                        else:
                            self.uses[stmt.i_grouping.arg] = \
                                self.WOOL['grouping'](stmt.i_grouping,
                                                      parent=self.top())

    def __getitem__(self, key):
        """
        Methode, that allows to access of the child elements directly as list
        of the top element
        :param key: name of the child elements which should be accessed
        :return: child object
        """

        return self.children[key]

    def __getattr__(self, name):
        """
        Methode, that allows to access a child element directly due the
        <parent>.<child> syntax

        :param name: name of the child element
        :return: child element object
        """

        key = name.replace('_', '-')
        try:
            return self.children[key]

        except KeyError:
            raise AttributeError("{!r} has no attribute {!r} or child {!r}"
                                 .format(self, name, key))

    def __dir__(self):
        """
        Mathode, that list all child elements as options of the auto completion

        :return: list of elements that are in the children list
        """
        return super().__dir__() + [key.replace('-', '_') for key in
                                    self.children]

    @template_var
    def all_children(self):
        """
        Collects a list of all child stmts of the current stmt regardless of the
        kind of implementation (local or import).
        :return: list of stmts
        """
        result = OrderedDict(self.children)
        result.update(self.uses)
        return result


class Module(Grouponder, yang='module'):
    """
    Wrapper class for a module statement.
    """

    def __init__(self, statement, parent=None):
        """
        Constructor for Class objects for module statements

        :param modules: Dictionary of classes of yang statements, where each
        class is a dictionary of all wrapped statements of the current module
        :param derived_types: Dictionary of all type defs which are used inside
        this module
        """
        self.all_nodes = {}
        self.derived_types = OrderedDict()
        super().__init__(statement, parent)
        # if self.statement.search_one('augment'):
        #     container = self.statement.search_one('augment').i_target_node
        #     self.WOOL.get(container.keyword)(container, self)


class Leaf(Typonder, yang='leaf'):
    """
    Wrapper class for type definition statements.

    :param path: used for leafrefs to store the reference path
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Container(Grouponder, yang='container'):
    """
    Wrapper class for container statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Enum(Typonder, yang='enum'):
    """
    Wrapper class for enum values.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Enumeration(Typonder, yang='enumeration'):
    """
    Wrapper class for enumeration statements.

    :param enums: Dictionary to store all wrapped enum objects
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.enums = OrderedDict()
        # loop through substatements and extract the enum values
        for stmt in statement.search('enum'):
            self.enums[stmt.arg] = self.WOOL['enum'](stmt, self)


class Union(Typonder, yang='union'):
    """
    Wrapper class for union statements

    :param types: Dictionary to store all types which are part of the union,
    stored as string or wrapped statement object
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # list of types that belong to the union
        self.types = OrderedDict()
        for stmt in statement.search('type'):
            if stmt.arg in TYPE_PATTERNS.keys():
                for pattern, wool_type_name in self.WOOL._data_type_patterns.\
                        items():
                    if re.match(pattern, stmt.arg):
                        self.types[wool_type_name] = wool_type_name
                        break
                else:
                    # additional compliance test that the type is a correct
                    # Yang type
                    self.types[stmt.arg] = TYPE_PATTERNS[stmt.arg]
            elif stmt.arg in self.top().derived_types.keys():
                key = stmt.arg
                self.types[stmt.arg] = self.top().derived_types.get(
                    key) or stmt.arg
            else:
                self.types[stmt.arg] = self.WOOL['typedef'](stmt,
                                                            parent=self.top())


class TypeDef(Typonder, yang='typedef'):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


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


class LeafList(Typonder, Listonder, yang='leaf-list'):
    """
    Wrapper class for leaf list statements.

    :param path: used for leafrefs to store the reference path
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Grouping(Grouponder, yang='grouping'):
    """
    Wrapper class for grouping statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class List(Grouponder, Listonder, yang='list'):
    """
    Wrapper class for list statements.

    :param keys: the values originally stored in the key substmt of an yang
    list stmt
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.keys = set()
        key_stmt = statement.search_one('key')
        if key_stmt is not None and key_stmt.arg is not None:
            # the key statement contains a space separated list of keys
            for key in key_stmt.arg.split():
                self.keys.add(key)


class Choice(Grouponder, yang='choice'):
    """
    Wrapper class for choice statements

    :param cases: Dictionary of all possible cases for the choice stmt
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.cases = OrderedDict()
        for case in self.statement.search('case'):
            self.cases[case.arg] = self.WOOL['case'](case, self)


class Case(Grouponder, yang='case'):
    """
    Wrapper class for case statements
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class RPC(Grouponder, yang='rpc'):
    """
    Parser for RPC nodes.

    :param input: stores the wrapped input statement
    :param output: stores the wrapped output statement
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        for item in self.statement.i_children:
            if item.keyword == 'input':
                self.input = self.WOOL['input'](item, self)
            elif item.keyword == 'output':
                self.output = self.WOOL['output'](item, self)


class Input(Grouponder, yang='input'):
    """
    Parser for input nodes.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Output(Grouponder, yang='output'):
    """
    Parser for output nodes.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
