import logging
import re
import sys
from collections import OrderedDict

import alpakka
from alpakka.wools import Wool
from alpakka.templates import template_var, create_context


WOOLS = alpakka.WOOLS


# configuration for logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


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
        :param parent: the wrapped parent statement of the current statement, None for the top element
        :param yang_stmt_type: yang type of the current statment, like module, container, list, leaf and so on
        :param yang_stmt_name: name of the current statement, is the same like in the original yang file
        :param description: string containing the description of the current statement provided by the yang file
        :param config: if the current statement has config substatement the value this one is stored in this variable
        """

        self.statement = statement
        self.parent = parent
        self.yang_stmt_type = statement.keyword
        self.yang_stmt_name = statement.arg
        for stmt in statement.substmts:

            if stmt.keyword == 'description' and stmt.arg.lower() != "none":
                self.description = stmt.arg
            elif stmt.keyword == 'config':
                self.config = statement.arg.lower() == 'true'

    @property
    def template_context(self):
        return create_context(self)

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

    @template_var
    def generate_key(self):
        """
        Generates a string which represents the path from the root element of the Statement to the target as unique
        key. In the case of imported Statements the string represents only the top element and the target element name
        :return: a unique key which is a human readable path to the module
        """
        key = ''
        # Key generation for elements which could be imported from other Modules or be implemented locally
        if self.yang_stmt_type == 'grouping' or self.yang_stmt_type == 'typedef':
            return self.statement.parent.arg + '/' + self.yang_stmt_name
        # Key generation for all other Statements
        else:
            if self.parent:
                key = self.parent.generate_key()

            return key + "/" + self.yang_stmt_name


class Typonder(NodeWrapper):
    """
    Base class for node wrappers that have a type property.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a typonder which extracts the data-type.

        :param data_type: string containing the argument of the type attribute of the yang statement
        :param is_build_in_type: boolean indicating is the data_type a yang base type or a typedef type
        :param enumeration: attribute containing the enumeration object if the data_type is enumeration
        :param union: attribute containing the union object if the data_type is union
        """
        super().__init__(statement, parent)
        if [i.arg for i in statement.substmts if i.keyword == 'type']:
            # processing if the yang type is a base type
            if [i.arg for i in statement.substmts if i.keyword == 'type'][0] in TYPE_PATTERNS.keys():
                self.data_type = TYPE_PATTERNS[[i.arg for i in statement.substmts if i.keyword == 'type'][0]]
                self.is_build_in_type = True
            # processing if the yang type is typedef
            else:
                self.data_type = [i.arg for i in statement.substmts if i.keyword == 'type'][0]
                # check is the typedef already generated
                if self.data_type not in self.top().derived_types.keys():
                    typedef = [i.i_typedef for i in statement.substmts if i.keyword == 'type'][0]
                    self.top().derived_types[self.data_type] = TypeDef(typedef, self.top())
                self.is_build_in_type = False

            # special processing if the data_type is enumeration
            if self.data_type == 'enumeration':
                enumeration = [i for i in statement.substmts if i.keyword == 'type'][0]
                self.enumeration = Enumeration(enumeration, self)
            # special processing if the data_type is an union
            elif self.data_type == 'union':
                union = [i for i in statement.substmts if i.keyword == 'type'][0]
                self.union = Union(union, self)


class Grouponder(NodeWrapper):
    """
    Base class for node wrappers that group variables.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a grouponder which extracts all statements which are childes of the current statement

        :param children: all wrapped statements which are children of this statement as list
        :param uses: if the current statement has a uses substmt a Grouping object created and stored in the uses var
        """
        super().__init__(statement, parent)
        self.uses = OrderedDict()
        self.children = OrderedDict()

        # the following line separates stmts which are imported with 'uses' from normal integrated stmts
        children_list = set(getattr(statement, 'i_children', [])).intersection(getattr(statement, 'substmts', []))

        # special handling for input and output stmt, because of the behavior which is similar to uses
        if statement.keyword == 'input' or statement.keyword == 'output':
            children_list = getattr(statement, 'i_children', [])

        # wrap all children of the node
        for child in children_list:
            child_wrapper = self.WOOL.get(child.keyword)
            if child_wrapper:
                self.children[child.arg] = child_wrapper(child, self)
            else:
                logging.debug("No wrapper for yang type: %s (%s)" %
                              (child.keyword, child.arg))

        # find all stmts which are imported with a 'uses' substmt and wrap the Grouping object related to ths uses
        for stmt in statement.substmts:
            if stmt.keyword == 'uses':
                # check is the used grouping already wrapped
                # if so, the wrapped grouping is linked in the 'uses' variable
                # if not a the grouping statement is wrapped
                if 'grouping' in self.top().modules:
                    if (stmt.i_grouping.parent.arg + '/' + stmt.i_grouping.arg) in self.top().modules['grouping']:
                        self.uses[stmt.i_grouping.arg] = self.top().modules['grouping'][(stmt.i_grouping.parent.arg + '/' + stmt.i_grouping.arg)]
                else:
                    self.uses[stmt.i_grouping.arg] = Grouping(stmt.i_grouping, self)


    @template_var
    def all_children(self):
        """
        Collects a list of all child stmts of the current stmt regardless of the kind of implementation (local or import).
        :return: list of stmts
        """
        return getattr(self.statement, 'i_children', [])


class Module(Grouponder, yang='module'):
    """
    Wrapper class for a module statement.
    """

    def __init__(self, statement, parent=None):
        """
        Constructor for Class objects for module statements

        :param modules: Dictionary of classes of yang statements, where each class is a dictionary of all wrapped statements of the current module
        :param derived_types: Dictionary of all type defs which are used inside this module
        """
        self.modules = OrderedDict()
        self.derived_types = OrderedDict()

        super().__init__(statement, parent)

        # append the wrapped module object to the modules dictionary for 'modules'
        self.modules['module'] = OrderedDict()
        self.modules['module'][self.generate_key()] = self

    @template_var
    def add_container(self, container_name, wrapped_description):
        """
        Add an Container object to the overall collection.

        :param container_name: the name of the Container
        :param wrapped_description: the wrapped node description
        """
        if 'container' not in self.modules:
            self.modules['container'] = OrderedDict()
            self.modules['container'][container_name] = wrapped_description
        elif container_name not in self.modules['container']:
            self.modules['container'][container_name] = wrapped_description

    @template_var
    def add_enumeration(self, enumeration_name, wrapped_description):
        """
        Add an Enumeration object to the overall collection.

        :param enumeration_name: the name of the Enumeration
        :param wrapped_description: the wrapped node description
        """
        if 'enumeration' not in self.modules:
            self.modules['enumeration'] = OrderedDict()
            self.modules['enumeration'][enumeration_name] = wrapped_description
        elif enumeration_name not in self.modules['enumeration']:
            self.modules['enumeration'][enumeration_name] = wrapped_description

    @template_var
    def add_list(self, list_name, wrapped_description):
        """
        Add an List object to the overall collection.

        :param list_name: the name of the List
        :param wrapped_description: the wrapped node description
        """
        if 'list' not in self.modules:
            self.modules['list'] = OrderedDict()
            self.modules['list'][list_name] = wrapped_description
        elif list_name not in self.modules['list']:
            self.modules['list'][list_name] = wrapped_description

    @template_var
    def add_grouping(self, grouping_name, wrapped_description):
        """
        Add an Grouping object to the overall collection.

        :param grouping_name: the name of the List
        :param wrapped_description: the wrapped node description
        """
        if 'grouping' not in self.modules:
            self.top().modules['grouping'] = OrderedDict()
            self.top().modules['grouping'][grouping_name] = wrapped_description
        elif grouping_name not in self.top().modules['grouping']:
            self.top().modules['grouping'][grouping_name] = wrapped_description

    @template_var
    def add_leaf(self, leaf_name, wrapped_description):
        """
        Add an Leaf object to the overall collection.

        :param leaf_name: the name of the Leaf
        :param wrapped_description: the wrapped node description
        """
        if 'leaf' not in self.modules:
            self.modules['leaf'] = OrderedDict()
            self.modules['leaf'][leaf_name] = wrapped_description
        elif leaf_name not in self.top().modules['leaf']:
            self.modules['leaf'][leaf_name] = wrapped_description

    @template_var
    def add_leaflist(self, leaflist_name, wrapped_description):
        """
        Add an Leaflist object to the overall collection.

        :param leaflist_name: the name of the Leaflist
        :param wrapped_description: the wrapped node description
        """
        if 'leaflist' not in self.modules:
            self.modules['leaflist'] = OrderedDict()
            self.modules['leaflist'][leaflist_name] = wrapped_description
        elif leaflist_name not in self.top().modules['leaflist']:
            self.modules['leaflist'][leaflist_name] = wrapped_description

    @template_var
    def add_rpc(self, rpc_name, wrapped_description):
        """
        Add an RPC object to the overall collection.

        :param rpc_name: the name of the RPC
        :param wrapped_description:  the wrapped node description
        """
        if 'rpc' not in self.modules:
            self.modules['rpc'] = OrderedDict()
            self.modules['rpc'][rpc_name] = wrapped_description
        elif rpc_name not in self.modules['rpc']:
            self.modules['rpc'][rpc_name] = wrapped_description

    @template_var
    def add_typedef(self, typedef_name, wrapped_description):
        """
        Add a type definition object to the overall collection.

        :param typedef_name: the name of the type definition
        :param wrapped_description: the wrapped node description
        """
        if 'typedef' not in self.modules:
            self.modules['typedef'] = OrderedDict()
            self.modules['typedef'][typedef_name] = wrapped_description
        elif typedef_name not in self.modules['typedef']:
            self.modules['typedef'][typedef_name] = wrapped_description

    @template_var
    def add_choice(self, choice_name, wrapped_description):
        """
        Add a choice object to the overall collection.

        :param choice_name: name of the choice object
        :param wrapped_description: wrapped description of the choice object
        """
        if 'choice' not in self.modules:
            self.modules['choice'] = OrderedDict()
            self.modules['choice'][choice_name] = wrapped_description
        elif choice_name not in self.modules['choice']:
            self.modules['choice'][choice_name] = wrapped_description

    @template_var
    def add_union(self, union_name, wrapped_description):
        """
        Add a union object to the overall collection.

        :param union_name: name of the union object
        :param wrapped_description: wrapped description of the union object
        """
        if 'union' not in self.modules:
            self.modules['union'] = OrderedDict()
            self.modules['union'][union_name] = wrapped_description
        elif union_name in self.modules['union']:
            self.modules['union'][union_name] = wrapped_description


class Leaf(Typonder, yang='leaf'):
    """
    Wrapper class for type definition statements.

    :param path: used for leafrefs to store the reference path
    """
    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        if self.data_type == 'leafref':
            self.path = [i.substmts[0].arg for i in statement.substmts if i.keyword == 'type'][0]
        self.top().add_leaf(self.generate_key(), self)

    @template_var
    def substmt_default(self):
        """
        Method to return the default value of the leaf if present, could be of different data type

        :return default: the default value of the leaf
        """
        for item in self.statement.substmts:
            if item.keyword == 'default':
                return item.arg

    @template_var
    def substmt_mandatory(self):
        """
        Method to return a boolean indicating is the leaf a mandatory one or not, if the substmt is present

        :return mandatory: boolean indicating mandatory or not
        """
        for item in self.statement.substmts:
            if item.keyword == 'mandatory':
                return item.arg


class Container(Grouponder, yang='container'):
    """
    Wrapper class for container statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.top().add_container(self.generate_key(), self)


class Enum(Typonder):
    """
    Wrapper class for enum values.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Enumeration(Typonder):
    """
    Wrapper class for enumeration statements.

    :param enums: Dictionary to store all wrapped enum objects
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.enums = OrderedDict()
        # loop through substatements and extract the enum values
        for stmt in statement.substmts:
            if stmt.keyword == 'enum':
                self.enums[stmt.arg] = Enum(stmt, self)


class Union(Typonder):
    """
    Wrapper class for union statements

    :param types: Dictionary to store all types which are part of the union, stored as string or wrapped statement object
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # list of types that belong to the union
        self.types = OrderedDict()
        for stmt in statement.substmts:
            if stmt.keyword == 'type':
                if stmt.arg in TYPE_PATTERNS.keys():
                    self.types[stmt.arg] = TYPE_PATTERNS[stmt.arg]
                # TODO: Muss auf die aktuelle key convention angepasst werden.
                elif stmt.arg in self.top().derived_types.keys():
                    self.types[stmt.arg] = self.top().derived_types[stmt.arg]
                else:
                    self.types[stmt.arg] = stmt.arg


class TypeDef(Typonder, yang='typedef'):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.top().add_typedef(self.generate_key(), self)

    @template_var
    def substmt_default(self):
        """
        Method to return the default value of the typedef if present, could be of different data type

        :return default: the default value of the typedef
        """
        for item in self.statement.substmts:
            if item.keyword == 'default':
                return item.arg


class Listonder():
    """
    Metaclass for all List type objects
    """

    def substmt_min_elements(self):
        """
        Method to return the minimum occurrence of list objects, if the respective substmt is present

        return: the number of minimum occurrence of list objects
        """
        for i in self.statement.substmts:
            if i.keyword == 'min-elements':
                return i.arg

    def substmt_max_elements(self):
        """
        Method to return the maximum occurrence of list objects, if the respective substmt is present

        return: the number of maximum occurrence of list objects
        """
        for i in self.statement.substmts:
            if i.keyword == 'max-elements':
                return i.arg


class LeafList(Typonder, Listonder, yang='leaf-list'):
    """
    Wrapper class for leaf list statements.

    :param path: used for leafrefs to store the reference path
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        if self.data_type == 'leafref':
            self.path = [i.substmts[0].arg for i in statement.substmts if i.keyword == 'type'][0]
        self.top().add_leaflist(self.generate_key(), self)


class Grouping(Grouponder, yang='grouping'):
    """
    Wrapper class for grouping statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.top().add_grouping(self.generate_key(), self)


class List(Grouponder, Listonder, yang='list'):
    """
    Wrapper class for list statements.

    :param key: key contains value which is originally stored in the key substmt of an yang list stmt
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        for i in statement.substmts:
            if i.keyword == 'key':
                self.key = i.arg
        self.top().add_list(self.generate_key(), self)


class Choice(Grouponder, yang='choice'):
    """
    Wrapper class for choice statements

    :param cases: Dictionary of all possible cases for the choice stmt
    """
    def __init__(self, statement, parent):
        super().__init__(statement, parent)

        self.cases = OrderedDict()
        for case in [i for i in self.statement.substmts if i.keyword == 'case']:
            self.cases[case.arg] = Case(case, self)

        self.top().add_choice(self.generate_key(), self)

    @template_var
    def substmt_default(self):
        """
        Method to return the default value of the choice if present, could be of different data type

        :return default: the default value of the choice
        """
        for item in self.statement.substmts:
            if item.keyword == 'default':
                return item.arg

    @template_var
    def substmt_mandatory(self):
        """
        Method to return a boolean indicating is the choice a mandatory one or not, if the substmt is present

        :return mandatory: boolean indicating mandatory or not
        """
        for item in self.statement.substmts:
            if item.keyword == 'mandatory':
                return item.arg


class Case(Grouponder):
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
        self.top().add_rpc(self.generate_key(), self)

        for item in self.statement.i_children:
            if item.keyword == 'input':
                self.input = Input(item, self)
            elif item.keyword == 'output':
                self.output = Output(item, self)


class Input(Grouponder):
    """
    Parser for input nodes.
    """
    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Output(Grouponder):
    """
    Parser for output nodes.
    """
    def __init__(self, statement, parent):
        super().__init__(statement, parent)
