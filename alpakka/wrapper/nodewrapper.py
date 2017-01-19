import re
from collections import OrderedDict

# Java type used to instantiate lists
JAVA_LIST_INSTANCE = {'com.google.common.collect.ImmutableList'}

# Java imports for using lists in an interface
JAVA_LIST_IMPORTS = {'java.util.List'}

# regular expressions mapping yang types to Java types
TYPE_PATTERNS_TO_JAVA = [
    (r"u?int\d*", "int"),
    (r"string", "String"),
    (r"boolean", "boolean"),
    (r"decimal64", "double"),
]

# Java wrapper classes for base types (needed for hashCode)
JAVA_WRAPPER_CLASSES = {
    "int": "Integer",
    "boolean": "Boolean",
    "double": "Double"
}


def type_to_java(yang):
    """
    Converts built-in YANG types to the corresponding Java types.

    :param yang: input YANG type string
    :return: Java type string or None
    """
    for pattern, java in TYPE_PATTERNS_TO_JAVA:
        if re.match(r'^%s$' % pattern, yang):
            return java
    raise ValueError("No Java type mapping for %s" % yang)


def java_class_name(name):
    """
    Cleanup for names that need to follow Java class name restrictions.
    Add any further processing here.
    :param name: the name to be cleaned up
    :return: class name following Java convention
    """
    class_name = name.capitalize()
    class_name = class_name.replace("-", " ").title()
    return class_name.replace(" ", "")


def to_camelcase(string):
    """
    Creates a camel case representation by removing hyphens.
    The first letter is lower case everything else remains untouched.
    Example: Hello-world -> helloWorld
    :param string: string to be processed
    :return: camel case representation of the string
    """
    string = string[0].lower() + string[1:]
    return re.sub(r'[-](?P<first>[a-z])',
                  lambda m: m.group('first').upper(), string)


class NodeWrapper:
    """
    Base class for node wrappers. It includes the base setup.
    """

    def __init__(self, statement, parent):
        self.statement = statement
        self.parent = parent
        for stmt in statement.substmts:
            if stmt.keyword == 'description' and stmt.arg.lower() != "none":
                self.description = stmt.arg
            elif stmt.keyword == 'config':
                self.config = statement.arg.lower() == 'true'

    def package(self):
        """
        The pakackage name of this module.
        :return: the package name
        """
        if self.statement.top:
            return self.statement.top.i_prefix.lower().replace("-", ".")
        else:
            return self.statement.i_prefix.lower().replace("-", ".")

    def subpath(self):
        """
        The subpath of this module.
        :return: the package name
        """
        if self.statement.top:
            return self.statement.top.i_prefix.lower().replace("-", "/")
        else:
            return self.statement.i_prefix.lower().replace("-", "/")

    def top(self):
        """
        Find the root wrapper object by walking the tree to the top.
        :return: the root node
        """
        if self.parent:
            return self.parent.top()
        else:
            return self


class Module(NodeWrapper):
    """
    Wrapper class for a module statement.
    """

    def __init__(self, statement, parent=None):
        super().__init__(statement, parent)
        self.java_name = java_class_name(statement.i_prefix)
        # prepare dictionaries
        self.typedefs = OrderedDict()
        self.rpcs = OrderedDict()
        self.classes = OrderedDict()
        # go through available substatements
        for stmt in statement.substmts:
            if stmt.keyword == 'typedef':
                typedef = TypeDef(stmt, self)
                self.typedefs[typedef.java_type] = typedef
            elif stmt.keyword == 'rpc':
                rpc = RPC(stmt, self)
                self.rpcs[rpc.java_name] = rpc
            elif stmt.keyword == 'grouping':
                grouping = Grouping(stmt, self)
                self.classes[grouping.java_type] = grouping
            else:
                print("Unhandled argument in module: %s" % stmt.arg)

    def enums(self):
        """
        Extracts the enumeration definitions from the typedefs.
        :return: dictionary of enums
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'enum'}

    def base_extensions(self):
        """
        Extracts extension of base types from the typedefs.
        :return: dictionary of base type extensions
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'base'}

    def unions(self):
        """
        Extracts all unions from the typedefs.
        :return:  dictionary of unions
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'union'}

    def rpc_imports(self):
        return {imp for _, data in getattr(self, 'rpcs', ())
                for imp in getattr(data, 'imports', ())}


class Typonder(NodeWrapper):
    """
    Base class for node wrappers that have a type property.
    """

    def __init__(self, statement, parent, is_external=False):
        """
        Constructor for a typonder that results in a type property.
        :param statement: the statement to be wrapped
        :param parent: the wrapper of the parent statement
        :param is_external: is the type defined outside of the module
        """
        super().__init__(statement, parent)
        self.is_external = is_external
        for stmt in statement.substmts:
            if stmt.keyword == 'type':
                # is the statement an enumeration
                if stmt.arg == 'enumeration':
                    self.type = Enumeration(stmt, self)
                # is the statement a base type
                elif any(re.match(r'^%s$' % pattern, stmt.arg) for pattern, _ in
                         TYPE_PATTERNS_TO_JAVA):
                    self.type = BaseType(stmt, self)
                # is the statement a union
                elif stmt.arg == 'union':
                    self.type = Union(stmt, self)
                # is the statement a lear reference
                elif stmt.arg == 'leafref':
                    self.type = LeafRef(stmt, self)
                # does the statement contain a type definition
                elif hasattr(stmt, 'i_typedef'):
                    self.type = TypeDef(stmt.i_typedef, self, is_external)


class BaseType(NodeWrapper):
    """
     Wrapper class for a java base types, like boolean, double, int and String.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_type = type_to_java(statement.arg)
        # is a cast needed to use hashCode
        self.java_cast = JAVA_WRAPPER_CLASSES.get(self.java_type, None)
        self.group = 'base'


class Enum(NodeWrapper):
    """
     Wrapper class for enum values.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # add an underscore in case the name starts with a number
        javaname = re.sub(r'^(\d)', r'_\1', statement.arg.upper())
        javaname = javaname.replace('-', '_').replace('.', '_')
        if javaname != statement.arg:
            self.javaname = javaname


class Enumeration(NodeWrapper):
    """
    Wrapper class for enumeration statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.enums = OrderedDict()
        self.group = 'enum'
        # loop through substatements and extract the enum values
        for stmt in statement.substmts:
            if stmt.keyword == 'enum':
                self.enums[stmt.arg] = Enum(stmt, self)

    def has_javanames(self):
        """
        Checks if at least one enum name was modified.
        :return: did enum names change
        """
        return any(hasattr(data, 'javaname') for _, data in self.enums.items())


class Union(Typonder):
    """
    Wrapper class for union statements
    """

    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent, is_external)
        self.group = 'union'
        self.type = None
        # list of types that belong to the union
        self.types = {}
        # look for type definitions
        for stmt in statement.substmts:
            if stmt.keyword == 'type':
                if hasattr(stmt, 'i_typedef'):
                    typedef = TypeDef(stmt.i_typedef, self)
                    self.types[to_camelcase(typedef.java_type)] = typedef


class TypeDef(Typonder):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent, is_external)
        self.group = 'type'
        self.java_type = java_class_name(statement.arg)
        self.java_imports = set()
        # for external types an import is added
        if is_external:
            self.java_imports.add('%s.%s' % (self.package(), self.java_type))


class Leaf(Typonder):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent, is_external)
        self.java_imports = set()
        self.java_type = self.type.java_type
        # if the package of the type differs from the lesf's type
        if self.package() != self.type.package():
            self.java_imports.add('%s.%s' % (self.type.package(), self.type.java_type))
        # if the type already has imports
        if hasattr(self.type, 'java_imports'):
            self.java_imports |= self.type.java_imports

    def interface_imports(self):
        """
        Set of imports that are needed if the interface is used.
        :return: set of imports
        """
        return self.java_imports


class LeafRef(NodeWrapper):
    """
    Wrapper class for leafref statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        type_spec = statement.i_type_spec
        # the target might not be defined for unused groupings
        if hasattr(type_spec, 'i_target_node'):
            self.group = 'ref'
            self.reference = Leaf(type_spec.i_target_node, self)
            self.java_type = self.reference.java_type
            # if the package of the node differs from the referenced type
            if self.package() != self.reference.package():
                self.java_imports = {'%s.%s' % (self.reference.package(), self.java_type)}


class LeafList(Typonder):
    """
    Wrapper class for leaf list statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.group = 'list'
        # if the type of the list elements is defined
        if hasattr(self, 'type') and hasattr(self.type, 'java_type'):
            self.java_type = 'List<%s>' % self.type.java_type
            # in case of leafrefs this attribute is available
            self.java_imports = getattr(self.type, 'java_imports', set())
            # this is used for typedefs
            if self.package() != self.type.package():
                self.java_imports.add('%s.%s' % (self.type.package(), self.type.java_type))
        # else we use a generic list
        else:
            self.java_type = 'List'

    def instance_imports(self):
        """
        Imports needed for instantiating this type.
        :return: instance imports
        """
        return JAVA_LIST_INSTANCE

    def internal_interface_imports(self):
        """
        Imports needed for interfaces inside the same module.
        :return: internal interface imports
        """
        return JAVA_LIST_IMPORTS

    def interface_imports(self):
        """
        Imports needed for an interface access.
        :return: interface imports
        """
        return JAVA_LIST_IMPORTS | getattr(self, 'java_imports', set())


class Grouponder(NodeWrapper):
    """
    Base class for node wrappers that group variables.
    """

    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent)
        self.is_external = is_external
        self.vars = OrderedDict()
        # find all available variables in the sub-statements
        for stmt in statement.substmts:
            keyword = stmt.keyword
            result = None
            # go through the supported variable types
            if keyword == 'leaf':
                result = Leaf(stmt, self, is_external)
            elif keyword == 'leaf-list':
                result = LeafList(stmt, self)
            elif keyword == 'grouping':
                result = Grouping(stmt, self, is_external)
            elif keyword == 'list':
                result = List(stmt, self, is_external)
            elif keyword == 'container':
                result = Container(stmt, self, is_external)
            # if a result is available add it to the variables
            if result is not None:
                # store the yang name
                result.name = stmt.arg
                # remove leading underscores from the name
                java_name = re.sub(r'^_', '', stmt.arg)
                java_name = to_camelcase(java_name)
                self.vars[java_name] = result

    def instance_imports(self):
        """
         Imports needed for instantiating this type.
         :return: instance imports
         """
        return {imp for data in self.vars.values()
                if hasattr(data, 'instance_imports')
                for imp in data.instance_imports()}

    def interface_imports(self):
        """
        Imports needed for an interface access.
        :return: interface imports
        """
        return {imp for data in self.vars.values()
                if data.interface_imports() is not None
                for imp in data.interface_imports()}


class Grouping(Grouponder):
    """
    Wrapper class for grouping statements.
    """

    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent, is_external)
        self.inherits = OrderedDict()
        for stmt in statement.substmts:
            if stmt.keyword == 'uses':
                class_name = java_class_name(stmt.i_grouping.arg)
                # if the module name does not match or we are assigned external
                if stmt.top.i_prefix != stmt.i_grouping.top.i_prefix or is_external:
                    self.inherits[class_name] = Grouping(stmt.i_grouping, self, True)
                # module internal inheritance
                else:
                    self.inherits[class_name] = Grouping(stmt.i_grouping, self)
        self.java_type = java_class_name(statement.arg)

    def type(self):
        if not self.vars:
            if len(self.inherits) == 1:
                return next(self.inherits.keys())
        return None

    def inherited_vars(self):
        """
        Collects a dictionary of inherited variables that are needed for super calls.
        :return: dictionary of inherited variables
        """
        result = OrderedDict()
        for name, parent_group in self.inherits.items():
            # collect variables that are inherited by the parent
            for inh_name, var in parent_group.inherited_vars().items():
                result[inh_name] = var
            # collect variables available in the parent class
            for var_name, var in parent_group.vars.items():
                result[var_name] = var
        return result

    def inheritance_imports(self):
        """
        Collects the set of imports that is needed due to inherited variables.
        :return: inheritance imports
        """
        result = set()
        # go through all super classes (hopefully one)
        for inherit in self.inherits.values():
            # if external we need to add all interface imports
            if inherit.is_external:
                result |= inherit.interface_imports()
            # check if the variables need an import, e.g. lists
            for var in inherit.vars.values():
                if hasattr(var, 'internal_interface_imports'):
                    result |= var.internal_interface_imports()
            # add recursive inheritance imports
            result |= inherit.inheritance_imports()
        return result

    def imports(self):
        """
        Collects all the imports that are needed for the grouping.
        :return: set of imports
        """
        # the import for the direct parent class
        extends = {'%s.%s' % (inherit.package(), name) for name, inherit in self.inherits.items()}
        return self.instance_imports() | self.interface_imports() | self.inheritance_imports() | extends


class Container(Grouping):
    """
    Wrapper class for container statements.
    """

    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent, is_external)
        self.java_import = set()
        for stmt in statement.substmts:
            if stmt.keyword == 'uses':
                # FIXME this only works for one uses
                self.java_type = java_class_name(stmt.i_grouping.arg)
                if stmt.i_grouping.top.i_prefix != stmt.top.i_prefix:
                    package = stmt.i_grouping.top.i_prefix.lower().replace("-", ".")
                    self.java_import.add(
                        '%s.%s' % (package, self.java_type))

    def interface_imports(self):
        """
        Imports needed for an interface access.
        :return: interface imports
        """
        return self.java_import


class List(Grouping):
    def __init__(self, statement, parent, is_external=False):
        super().__init__(statement, parent, is_external)
        self.group = 'list'
        for stmt in statement.substmts:
            if stmt.keyword == 'uses':
                self.type = Grouping(stmt.i_grouping, self)
                if self.package() != self.type.package() or is_external:
                    self.java_import = {'%s.%s' % (self.type.package(), self.type.java_type)}
        if hasattr(self, 'type') and hasattr(self.type, 'java_type'):
            self.java_type = 'List<%s>' % self.type.java_type
        else:
            self.java_type = 'List'

    def instance_imports(self):
        return JAVA_LIST_INSTANCE

    def internal_interface_imports(self):
        """
        Imports needed for interfaces inside the same module.
        :return: internal interface imports
        """
        return JAVA_LIST_IMPORTS

    def interface_imports(self):
        return JAVA_LIST_IMPORTS | getattr(self, 'java_import', set())


class Input(Grouponder):
    """
    Parser for input nodes.
    """
    pass


class Output(Grouponder):
    """
    Parser for output nodes.
    """
    pass


class RPC(NodeWrapper):
    """
    Parser for RPC nodes.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_name = to_camelcase(statement.arg)
        for stmt in statement.substmts:
            if stmt.keyword == 'input':
                self.input = Input(stmt, self)
            elif stmt.keyword == 'output':
                self.output = Output(stmt, self)

    def imports(self):
        # currently only input imports are needed
        if hasattr(self, 'input'):
            return self.input.interface_imports()
        else:
            return set()
