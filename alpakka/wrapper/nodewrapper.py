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
        # members that are available for all nodes
        self.statement = statement
        self.parent = parent
        self.yang_type = statement.keyword
        # the yang module name
        self.yang_module_name = statement.arg
        # statements that might be available in general
        for stmt in statement.substmts:
            # store the description if available
            if stmt.keyword == 'description' and stmt.arg.lower() != "none":
                self.description = stmt.arg
            # is the node configurable
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
        key = ''
        if self.parent:
            key = self.parent.generate_key()

        return key + "/" + self.yang_module_name


class Typonder(NodeWrapper):
    """
    Base class for node wrappers that have a type property.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a typonder which extracts the data-type.

        :param statement: the statement to be wrapped
        :param parent: the wrapper of the parent statement
        """
        super().__init__(statement, parent)
        if [i.arg for i in statement.substmts if i.keyword == 'type']:
            if [i.arg for i in statement.substmts if i.keyword == 'type'][0] in TYPE_PATTERNS.keys():
                self.data_type = TYPE_PATTERNS[[i.arg for i in statement.substmts if i.keyword == 'type'][0]]
                self.is_build_in_type = True
            else:
                self.data_type = [i.arg for i in statement.substmts if i.keyword == 'type'][0]
                if self.data_type not in self.top().derived_types.keys():
                    typedef = self.top().statement.i_typedefs[self.data_type]
                    self.top().children[self.data_type] = TypeDef(typedef, self.top())
                self.is_build_in_type = False

            if self.data_type == 'enumeration':
                enumeration = [i for i in statement.substmts if i.keyword == 'type'][0]
                self.enumeration = Enumeration(enumeration, self)

            elif self.data_type == 'union':
                union = [i for i in statement.substmts if i.keyword == 'type'][0]
                self.union = Union(union, self)


class Grouponder(NodeWrapper):
    """
    Base class for node wrappers that group variables.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.uses = OrderedDict()
        self.children = OrderedDict()

        # the following line separates stmts which are imported with 'uses' from normal integrated stmts
        children_list = set(getattr(statement, 'i_children', [])).intersection(getattr(statement, 'substmts', []))

        # wrap all children of the node
        for child in children_list:
            child_wrapper = self.WOOL.get(child.keyword)
            if child_wrapper:
                self.children[child.arg] = child_wrapper(child, self)
            else:
                logging.debug("No wrapper for yang type: %s (%s)" %
                              (child.keyword, child.arg))

        # find all stmts which are imported with a 'uses' substmt
        for stmt in statement.substmts:
            if stmt.keyword == 'uses':
                # class name for the import
                grouping_name = stmt.i_grouping.arg
                # add the grouping to the list of super classes
                self.uses[grouping_name] = Grouping(stmt.i_grouping, self)

    @template_var
    def all_children(self):
        """
        Collects a list of all child stmts of the current stmt regardless of the kind of import.
        :return: list of stmts
        """
        return getattr(self.statement, 'i_children', [])


class Module(Grouponder, yang='module'):
    """
    Wrapper class for a module statement.
    """

    def __init__(self, statement, parent=None):
        # IMPORTANT: prepare dictionaries before calling super init!
        self.modules = OrderedDict()
        self.derived_types = OrderedDict()

        super().__init__(statement, parent)

        self.modules['module'] = OrderedDict()
        self.modules['module'][self.generate_key()] = self
        # call the super constructor
        # store the java name of the module

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
    """
    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        if self.data_type == 'leafref':
            self.path = [i.substmts[0].arg for i in statement.substmts if i.keyword == 'type'][0]
        self.top().add_leaf(self.generate_key(), self)

    @template_var
    def substmt_default(self):
        return [item.arg for item in self.statement.substmts if item.keyword == 'default'][0]

    @template_var
    def substmt_mandatory(self):
        return [item.arg for item in self.statement.substmts if item.keyword == 'mandatory'][0]


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
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # list of types that belong to the union
        self.types = OrderedDict()
        for stmt in statement.substmts:
            if stmt.keyword == 'type':
                if stmt.arg in TYPE_PATTERNS.keys():
                    self.types[stmt.arg] = TYPE_PATTERNS[stmt.arg]
                elif stmt.arg in self.top().derived_types.keys():
                    self.types[stmt.arg] = self.top().derived_types[stmt.arg]
                else:
                    self.types[stmt.arg] = stmt.arg

# TODO: @Felix from here on old code


class TypeDef(Typonder, yang='typedef'):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        if statement.arg not in self.top().derived_types.keys():
            self.top().derived_types[statement.arg] = self
            self.top().add_typedef(self.generate_key(), self)

    @template_var
    def substmt_default(self):
        return [item.arg for item in self.statement.substmts if item.keyword == 'default'][0]


class Listonder():
    """
    Metaclass for all List type objects
    """

    def substmt_min_elements(self):
        return [i.arg for i in self.statement.substmts if i.keyword == 'min-elements'][0]

    def substmt_max_elements(self):
        return [i.arg for i in self.statement.substmts if i.keyword == 'max-elements'][0]


class LeafList(Typonder, Listonder, yang='leaf-list'):
    """
    Wrapper class for leaf list statements.
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
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.key = [i.arg for i in statement.substmts if i.keyword == 'key'][0]
        self.top().add_list(self.generate_key(), self)


class Choice(Grouponder, yang='choice'):

    def __init__(self, statement, parent):
        super().__init__(statement, parent)

        self.cases = OrderedDict()
        case_list = [i for i in self.statement.substmts if i.keyword == 'case']
        for case in case_list:
            self.cases[case.arg] = Case(case, self)

        self.top().add_choice(self.generate_key(), self)

    @template_var
    def substmt_default(self):
        return [item.arg for item in self.statement.substmts if item.keyword == 'default'][0]

    @template_var
    def substmt_mandatory(self):
        return [item.arg for item in self.statement.substmts if item.keyword == 'mandatory'][0]


class Case(Grouponder):

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class RPC(Grouponder, yang='rpc'):
    """
    Parser for RPC nodes.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.top().add_rpc(self.generate_key(), self)

        for item in self.statement:
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