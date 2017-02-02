import logging
import re
from collections import OrderedDict

# configuration for logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

# appendix indicating a list type class
JAVA_LIST_CLASS_APPENDIX = 'ListType'

# Java imports for using lists in an interface
JAVA_LIST_IMPORTS = ('java.util', 'List')

# Java type used to instantiate lists
JAVA_LIST_INSTANCE_IMPORTS = ('com.google.common.collect', 'ImmutableList')

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


class ImportDict:
    """
    Class that is used to store imports. It wraps a dictionary and stores the classes per package.
    This makes it easier to filter imports that are part of a package.
    """

    def __init__(self):
        # an empty dictionary
        self.imports = {}

    def add_import(self, package, clazz):
        """
        Adds an import.
        :param package: the package of the import
        :param clazz: the class of the import
        """
        if package in self.imports:
            self.imports[package].add(clazz)
        else:
            self.imports[package] = {clazz}

    def merge(self, other):
        """
        Merges another dictionary into this one.
        :param other: the dict to be merged
        """
        for package, classes in other.imports.items():
            if package not in self.imports:
                self.imports[package] = set()
            self.imports[package] |= classes

    def get_imports(self):
        """
        Converts the managed imports into a set of imports.
        :return: a set of import strings
        """
        imports = set()
        for package, classes in self.imports.items():
            for cls in classes:
                imports.add('%s.%s' % (package, cls))
        return imports


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
        # members that are available for all nodes
        self.statement = statement
        self.parent = parent
        self.children = {}
        # the yang module name
        if self.statement.top:
            self.yang_module = self.statement.top.i_modulename
        else:
            self.yang_module = self.statement.i_modulename
        # wrap all children of the node
        for child in getattr(statement, 'i_children', []):
            child_wrapper = YANG_NODE_TO_WRAPPER.get(child.keyword, None)
            if child_wrapper:
                self.children[child.arg] = child_wrapper(child, self)
            else:
                logging.info("No wrapper for yang type: %s (%s)" % (child.keyword, child.arg))
        # statements that might be available in general
        for stmt in statement.substmts:
            # store the description if available
            if stmt.keyword == 'description' and stmt.arg.lower() != "none":
                self.description = stmt.arg
            # is the node configurable
            elif stmt.keyword == 'config':
                self.config = statement.arg.lower() == 'true'

    def package(self):
        """
        The pakackage name of this module.
        :return: the package name
        """
        return self.yang_module.lower().replace("-", ".")

    def subpath(self):
        """
        The subpath of this module.
        :return: the package name
        """
        return self.yang_module.lower().replace("-", "/")

    def top(self):
        """
        Find the root wrapper object by walking the tree recursively to the top.
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
        # IMPORTANT: prepare dictionaries before calling super init!
        self.classes = OrderedDict()
        self.rpcs = OrderedDict()
        self.typedefs = OrderedDict()
        # call the super constructor
        super().__init__(statement, parent)
        # store the java name of the module
        self.java_name = java_class_name(statement.i_prefix)

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

    def types(self):
        """
        Extracts extension of defined types from the typedefs.
        :return: dictionary of type extensions
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'type'}

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

    def add_class(self, class_name, wrapped_description):
        """
        Add a class to the collection that needs to be generated.
        :param class_name: the class name to be used
        :param wrapped_description: the wrapped node description
        """
        # TODO: might need additional processing
        if class_name in self.classes.keys():
            logging.debug("Class already in the list: %s", class_name)
            if len(wrapped_description.children) != len(self.classes[class_name].children):
                logging.warning("Number of children does not match for %s", class_name)
        else:
            self.classes[class_name] = wrapped_description

    def del_class(self, class_name):
        """
        Deletes a class from the collection.
        :param class_name: the class to be removed
        """
        self.classes.pop(class_name)

    def add_rpc(self, rpc_name, wrapped_description):
        """
        Add an RPC that needs to be generated.
        :param rpc_name: the name of the RPC
        :param wrapped_description:  the wrapped node description
        """
        self.rpcs[rpc_name] = wrapped_description

    def add_typedef(self, typedef_name, wrapped_description):
        """
        Add a type definition that needs to be generated.
        :param typedef_name: the name of the type definition
        :param wrapped_description: the wrapped node description
        """
        # TODO: might need additional processing
        self.typedefs[typedef_name] = wrapped_description


class Typonder(NodeWrapper):
    """
    Base class for node wrappers that have a type property.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a typonder that results in a type property.
        :param statement: the statement to be wrapped
        :param parent: the wrapper of the parent statement
        """
        super().__init__(statement, parent)
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
                    self.type = TypeDef(stmt.i_typedef, self)
                else:
                    logging.warning("Unmatched type: %s", stmt.arg)

    def member_imports(self):
        """
        :return: Imports that are needed for this type if it is a member of a class.
        """
        return self.type.java_imports


class BaseType(NodeWrapper):
    """
     Wrapper class for a java base types, like boolean, double, int and String.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        self.java_type = type_to_java(statement.arg)
        # is a cast needed to use hashCode
        self.java_cast = JAVA_WRAPPER_CLASSES.get(self.java_type, None)
        self.group = 'base'
        self.is_base = True


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
        self.java_imports = ImportDict()
        self.java_imports.add_import(self.package(), java_class_name(self.statement.arg))
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


class Union(NodeWrapper):
    """
    Wrapper class for union statements
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.group = 'union'
        self.type = None
        # list of types that belong to the union
        self.types = {}
        # FIXME: collect the imports
        self.java_imports = OrderedDict()
        # look for type definitions
        for stmt in statement.substmts:
            if stmt.keyword == 'type':
                # is the statement a base type
                if any(re.match(r'^%s$' % pattern, stmt.arg) for pattern, _ in
                       TYPE_PATTERNS_TO_JAVA):
                    self.type = BaseType(stmt, self)
                elif hasattr(stmt, 'i_typedef'):
                    typedef = TypeDef(stmt.i_typedef, self)
                    self.types[to_camelcase(typedef.java_type)] = typedef


class TypeDef(Typonder):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.group = 'type'
        self.java_type = java_class_name(statement.arg)
        # for external types an import is added
        self.java_imports = ImportDict()
        self.java_imports.add_import(self.package(), self.java_type)
        # add type definition
        self.top().add_typedef(self.java_type, self)


class Leaf(Typonder):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_type = self.type.java_type
        self.java_imports = ImportDict()
        self.java_imports.merge(self.type.java_imports)


class LeafRef(NodeWrapper):
    """
    Wrapper class for leafref statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        type_spec = statement.i_type_spec
        # The target is defined in the module tree but might not be for unused groupings.
        if hasattr(type_spec, 'i_target_node'):
            self.group = 'ref'
            self.reference = Leaf(type_spec.i_target_node, self)
            self.java_type = self.reference.java_type
            self.java_imports.add_import(self.reference.package(), self.java_type)


class LeafList(Typonder):
    """
    Wrapper class for leaf list statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        self.java_imports.add_import(JAVA_LIST_IMPORTS[0], JAVA_LIST_IMPORTS[1])
        self.group = 'list'
        # if the type of the list elements is defined
        if hasattr(self, 'type') and hasattr(self.type, 'java_type'):
            self.java_type = 'List<%s>' % self.type.java_type
            # in case of leafrefs this attribute is available
            self.java_imports.merge(self.type.java_imports)
        # else we use a generic list
        else:
            self.java_type = 'List'


class Grouponder(NodeWrapper):
    """
    Base class for node wrappers that group variables.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.vars = OrderedDict()
        self.uses = OrderedDict()
        # find all available variables in the sub-statements
        for stmt in statement.substmts:
            keyword = stmt.keyword
            result = None
            # go through the supported variable types
            if keyword == 'leaf':
                result = Leaf(stmt, self)
            elif keyword == 'leaf-list':
                result = LeafList(stmt, self)
            elif keyword == 'grouping':
                result = Grouping(stmt, self)
            elif keyword == 'list':
                result = List(stmt, self)
            elif keyword == 'container':
                result = Container(stmt, self)
            elif stmt.keyword == 'uses':
                # class name for the import
                class_name = java_class_name(stmt.i_grouping.arg)
                # add the grouping to the list of super classes
                self.uses[class_name] = Grouping(stmt.i_grouping, self)
                self.top().add_class(class_name, self.uses[class_name])
            # if a result is available add it to the variables
            if result is not None:
                # store the yang name
                result.name = stmt.arg
                # remove leading underscores from the name
                java_name = re.sub(r'^_', '', stmt.arg)
                java_name = to_camelcase(java_name)
                self.vars[java_name] = result

    def inherited_vars(self):
        """
        Collects a dictionary of inherited variables that are needed for super calls.
        :return: dictionary of inherited variables
        """
        result = OrderedDict()
        for name, parent_group in self.uses.items():
            # collect variables that are inherited by the parent
            for inh_name, var in parent_group.inherited_vars().items():
                result[inh_name] = var
            # collect variables available in the parent class
            for var_name, var in parent_group.vars.items():
                result[var_name] = var
        return result

    def imports(self):
        """
        Collects all the imports that are needed for the grouping.
        :return: set of imports
        """
        imports = ImportDict()
        # imports from children
        for child in self.children.values():
            imports.merge(child.java_imports)
        # imports from super classes
        for inherit in self.uses.values():
            imports.merge(inherit.inheritance_imports())
        for var in self.vars.values():
            # checking if there is at least one list defined in the grouponder
            if hasattr(var, 'group') and var.group == 'list':
                imports.add_import(JAVA_LIST_INSTANCE_IMPORTS[0], JAVA_LIST_INSTANCE_IMPORTS[1])
                break
        return imports.get_imports()


class Grouping(Grouponder):
    """
    Wrapper class for grouping statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # own Java type name
        self.java_type = java_class_name(statement.arg)
        self.java_imports = ImportDict()
        self.java_imports.add_import(self.package(), self.java_type)

    def type(self):
        # FIXME: needs fixing for more than one uses
        if not self.vars:
            if len(self.uses) == 1:
                return next(self.uses.keys())
        return None

    def inheritance_imports(self):
        """
        :return: Imports needed if inheriting from this class.
        """
        return self.java_imports

    def member_imports(self):
        return self.java_imports


class Container(Grouponder):
    """
    Wrapper class for container statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        # this container results in a java class
        if 'tapi' in self.top().yang_module and self.parent == self.top():
            # fixing name collision in the ONF TAPI: context
            self.java_type = java_class_name(statement.arg) + "Top"
            for name in self.uses.keys():
                self.uses.pop(name)
                self.top().del_class(name)
            for ch_name, ch_wrapper in self.children.items():
                # store the yang name
                ch_wrapper.name = ch_wrapper.statement.arg
                # remove leading underscores from the name
                java_name = re.sub(r'^_', '', ch_wrapper.name)
                java_name = to_camelcase(java_name)
                self.vars[java_name] = ch_wrapper
                self.top().add_class(self.java_type, self)
                self.java_imports.add_import(self.package(), self.java_type)
        # containers that just import a grouping don't need a new class -> variable
        elif len(self.uses) == 1 and len(self.vars) == 0:
            class_item = next(iter(self.uses.values()))
            self.java_type = class_item.java_type
            self.java_imports = class_item.member_imports()
        else:
            self.java_type = java_class_name(statement.arg)
            self.top().add_class(self.java_type, self)
            self.java_imports.add_import(self.package(), self.java_type)

    def member_imports(self):
        """
        :return: imports needed if this class is a member
        """
        return self.java_imports


class List(Grouponder):
    """
    Wrapper class for list statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.group = 'list'
        self.java_imports = ImportDict()
        self.java_imports.add_import(JAVA_LIST_IMPORTS[0], JAVA_LIST_IMPORTS[1])
        # check if a super class exists and assign type
        if self.uses:
            self.type = next(iter(self.uses.values()))
            self.java_imports.merge(self.type.inheritance_imports())
        # if new variables are defined in the list, a helper class is needed
        if self.children and 0 < len(self.vars):
            self.element_type = java_class_name(statement.arg) + JAVA_LIST_CLASS_APPENDIX
            self.top().add_class(self.element_type, self)
            self.java_type = 'List<%s>' % self.element_type
        else:
            # if a type is defined use it
            if hasattr(self, 'type') and hasattr(self.type, 'java_type'):
                self.element_type = self.type.java_type
                self.java_type = 'List<%s>' % self.type.java_type
            # unknown list elements
            else:
                self.java_type = 'List'


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
        self.top().add_rpc(self.java_name, self)

        # def imports(self):
        #     # currently only input imports are needed
        #     if hasattr(self, 'input'):
        #         return self.input.interface_imports()
        #     else:
        #         return set()


YANG_NODE_TO_WRAPPER = {
    "container": Container,
    "typedef": TypeDef,
    "rpc": RPC,
    "grouping": Grouping,
    "list": List,
    "leaf": Leaf,
    "input": Input,
    "output": Output,
    "leaf-list": LeafList,
}
