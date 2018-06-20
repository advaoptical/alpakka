from alpakka.wrapper.nodewrapper import NodeWrapper
from alpakka.wrapper.nodewrapper import Listonder
from alpakka.templates import template_var
from collections import OrderedDict
import re
import alpakka

WOOLS = alpakka.WOOLS

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


class Leaf(Typonder, yang='leaf'):
    """
    Wrapper class for type definition statements.

    :param path: used for leafrefs to store the reference path
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


class LeafList(Typonder, Listonder, yang='leaf-list'):
    """
    Wrapper class for leaf list statements.

    :param path: used for leafrefs to store the reference path
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
