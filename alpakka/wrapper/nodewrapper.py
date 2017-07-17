import logging
import re
import sys
from collections import OrderedDict

import alpakka
from alpakka.wools import Wool
from alpakka.templates import template_var


WOOLS = alpakka.WOOLS


# configuration for logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


# appendix indicating a list type class
JAVA_LIST_CLASS_APPENDIX = 'ListType'

# Java imports for using lists in an interface
JAVA_LIST_IMPORTS = ('java.util', 'List')

# Java type used to instantiate lists
JAVA_LIST_INSTANCE_IMPORTS = ('com.google.common.collect', 'ImmutableList')

# list of reserved words in Java
JAVA_RESERVED_WORDS = frozenset(["switch", "case"])

# regular expressions mapping yang types to Java types
TYPE_PATTERNS_TO_JAVA = [
    (r"u?int\d*", "int"),
    (r"string", "String"),
    (r"boolean", "boolean"),
    (r"decimal64", "double"),
    (r"binary", "byte[]"),
    (r"empty", "Object"),
]

# Java wrapper classes for base types (needed for hashCode)
JAVA_WRAPPER_CLASSES = {
    "int": "Integer",
    "boolean": "Boolean",
    "double": "Double"
}


class ImportDict:
    """
    Class that is used to store imports.

    It wraps a dictionary and stores the classes per package as sets.
    This makes it easier to filter imports that are part of a package.

    >>> impdict = ImportDict()
    >>> impdict.add_import('package', 'Class')
    >>> impdict.imports
    {'package': {'Class'}}
    >>> impdict.get_imports()
    {'package.Class'}

    Newly added imports are merged into the existing ones:

    >>> impdict.add_import('package', 'Clazz')
    >>> sorted(impdict.imports['package'])
    ['Class', 'Clazz']
    >>> sorted(impdict.get_imports())
    ['package.Class', 'package.Clazz']

    You can also merge an ``ImportDict`` with another one:

    >>> other = ImportDict()
    >>> other.add_import('package', 'Class')
    >>> other.add_import('package', 'Klass')
    >>> other.add_import('fancy.package', 'Klazz')

    >>> impdict.merge(other)
    >>> sorted(impdict.imports.keys())
    ['fancy.package', 'package']
    >>> sorted(impdict.get_imports())
    ['fancy.package.Klazz', 'package.Class', 'package.Clazz', 'package.Klass']
    """

    def __init__(self):
        # an empty dictionary
        self.imports = {}

    def add_import(self, package, clazz):
        """
        Adds an import.

        :param package: the package name of the import
        :param clazz: the class name of the import
        """
        self.imports.setdefault(package, set()).add(clazz)

    def merge(self, other):
        """
        Merges another dictionary into this one.

        :param other: the :class:`ImportDict` instance to be merged
        """
        for package, classes in other.imports.items():
            pkgclasses = self.imports.setdefault(package, set())
            pkgclasses |= classes

    def get_imports(self):
        """
        Converts the managed imports into a set of imports.

        :return: a ``set`` of fully qualified import strings
        """
        return {'%s.%s' % (pkg, cls) for pkg, classes in self.imports.items()
                for cls in classes}


def type_to_java(yang):
    """
    Converts built-in YANG types to the corresponding Java types.

    If no mapping is available, a ``ValueError`` is raised.

    :param yang: input YANG type string
    :return: Java type string

    >>> type_to_java('int32')
    'int'
    >>> type_to_java('uint16')
    'int'
    >>> type_to_java('empty')
    'Object'

    >>> type_to_java('invalid')
    Traceback (most recent call last):
      ...
    ValueError: No Java type mapping for 'invalid'
    """
    for pattern, java in TYPE_PATTERNS_TO_JAVA:
        if re.match(r'^%s$' % pattern, yang):
            return java

    raise ValueError("No Java type mapping for %s" % repr(yang))


def java_class_name(name):
    """
    Cleanup for names that need to follow Java class name restrictions.
    Add any further processing here.

    :param name: the name to be cleaned up
    :return: class name following Java convention

    >>> java_class_name('some-type')
    'SomeType'
    """
    return name.replace("-", " ").title().replace(" ", "")


def to_camelcase(string):
    """
    Creates a camel case representation by removing hyphens.
    The first letter is lower case everything else remains untouched.

    :param string: string to be processed
    :return: camel case representation of the string

    >>> to_camelcase('Hello-world')
    'helloWorld'
    """
    name = string[0].lower() + string[1:]
    name = re.sub(r'[-](?P<first>[a-zA-Z])',
                  lambda m: m.group('first').upper(),
                  name)
    # check if the name is a reserved word and prepend '_'
    if name in JAVA_RESERVED_WORDS:
        return '_' + name
    else:
        return name


def to_package(string, prefix=None):
    """
    Converts the string to a package name by making it lower case,
    replacing '-' with '.' and adding a prefix if available.

    :param string: the string to be converted
    :param prefix: the prefix for the package
    :return: package name

    >>> to_package('yang-module')
    'yang.module'

    >>> to_package('yang-module', 'fancy')
    'fancy.yang.module'
    """
    package = string.lower().replace("-", ".")
    if prefix:
        package = '%s.%s' % (prefix, package)
    return package


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
        self.children = OrderedDict()
        # the yang module name
        self.yang_module = (self.statement.top or self.statement).i_modulename
        # wrap all children of the node
        for child in getattr(statement, 'i_children', []):
            child_wrapper = self.WOOL.get(child.keyword)
            if child_wrapper:
                # START of special handling for choice statements:
                if child.keyword == 'choice':
                    # skip adding the choice statement to the tree
                    child_wrapper(child, self)
                elif self.statement.keyword == 'choice':
                    # add child case statements to the parent, not to self
                    parent.children[child.arg] = child_wrapper(child, self)
                # END of special handling for choice statement
                else:
                    self.children[child.arg] = child_wrapper(child, self)
            else:
                logging.debug("No wrapper for yang type: %s (%s)" %
                              (child.keyword, child.arg))
        # statements that might be available in general
        for stmt in statement.substmts:
            # store the description if available
            if stmt.keyword == 'description' and stmt.arg.lower() != "none":
                self.description = stmt.arg
            # is the node configurable
            elif stmt.keyword == 'config':
                self.config = statement.arg.lower() == 'true'

    @template_var
    def package(self):
        """
        The pakackage name of this module.
        :return: the package name
        """
        return to_package(self.yang_module, NodeWrapper.prefix)

    @template_var
    def subpath(self):
        """
        The subpath of this module.
        :return: the package name
        """
        if NodeWrapper.prefix:
            return '%s/%s' % (NodeWrapper.prefix.replace(".", "/"),
                              self.yang_module.lower().replace("-", "/"))
        else:
            return self.yang_module.lower().replace("-", "/")

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

    def collect_keys(self, only_parents=False):
        """
        Collects the list keys all the way up through the hierarchy.

        :param only_parents: flag that decides if the own keys are skipped
        :return: list of keys
        """
        result = self.parent and self.parent.collect_keys() or []
        if not only_parents:
            result += getattr(self, 'keys', ())
        return result


class Module(NodeWrapper, yang='module'):
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

    @template_var
    def enums(self):
        """
        Extracts the enumeration definitions from the typedefs.

        :return: dictionary of enums
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'enum'}

    @template_var
    def base_extensions(self):
        """
        Extracts extension of base types from the typedefs.

        :return: dictionary of base type extensions
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'base'}

    @template_var
    def types(self):
        """
        Extracts extension of defined types from the typedefs.

        :return: dictionary of type extensions
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'type'}

    @template_var
    def unions(self):
        """
        Extracts all unions from the typedefs.

        :return:  dictionary of unions
        """
        return {name: data for name, data in self.typedefs.items()
                if data.type.group == 'union'}

    @template_var
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
            if len(wrapped_description.children) != len(
                    self.classes[class_name].children
            ):
                logging.warning(
                    "Number of children mismatch for %s between stored "
                    "module %s and new module %s",
                    class_name, self.classes[class_name].yang_module,
                    self.yang_module)
            # print(self.classes[class_name].children.keys())
            old = set(self.classes[class_name].children.keys())
            new = set(wrapped_description.children.keys())
            # print the different children
            diff = old ^ new
            if diff:
                logging.warning(
                    "Child mismatch for class %s between module %s and %s: %s",
                    class_name, self.classes[class_name].yang_module,
                    self.yang_module, diff)
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
                elif any(re.match(r'^%s$' % pattern, stmt.arg)
                         for pattern, _ in TYPE_PATTERNS_TO_JAVA):
                    self.type = BaseType(stmt, self)
                # is the statement a union
                elif stmt.arg == 'union':
                    self.type = Union(stmt, self)
                # is the statement a lear reference
                elif stmt.arg == 'leafref':
                    self.type = LeafRef(stmt, self)
                elif stmt.arg == 'bits':
                    self.type = Bits(statement, self)
                # does the statement contain a type definition
                elif hasattr(stmt, 'i_typedef'):
                    self.type = TypeDef(stmt.i_typedef, self)
                else:
                    logging.warning("Unmatched type: %s", stmt.arg)

    @template_var
    def member_imports(self):
        """
        :return: Imports that are needed for this type if it is a member of a
                 class.
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


"""
alternative class wrapper for bits and bit structure
"""


class Bits(NodeWrapper):
    """
    Wrapper class for bits statement
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        self.java_type = java_class_name(self.statement.arg)
        self.java_imports.add_import(self.package(), self.java_type)
        self.bits = OrderedDict()
        self.group = 'bits'
        for stmt in statement.substmts:
            if stmt.keyword == 'bit':
                self.bits[stmt.arg] = Bit(stmt, self)


class Bit(NodeWrapper, yang='bit'):
    """
    Wrapper class for bit values.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        javaname = statement.arg
        javaname = javaname.replace('-', '_').replace('.', '_')
        self.javaname = javaname


class Enum(NodeWrapper, yang='enum'):
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
        self.java_type = java_class_name(self.statement.arg)
        self.java_imports.add_import(
            self.package(), java_class_name(self.parent.statement.arg))
        self.enums = OrderedDict()
        self.group = 'enum'
        # loop through substatements and extract the enum values
        for stmt in statement.substmts:
            if stmt.keyword == 'enum':
                self.enums[stmt.arg] = Enum(stmt, self)

    @template_var
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
        self.java_imports = ImportDict()
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
                    package = to_package(stmt.i_typedef.i_module.arg,
                                         NodeWrapper.prefix)
                    self.java_imports.add_import(package, typedef.java_type)


class TypeDef(Typonder, yang='typedef'):
    """
    Wrapper class for type definition statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.group = 'type'
        self.java_imports = ImportDict()
        if self.type.group == 'ref':
            self.java_type = self.type.java_type
            self.java_imports.merge(self.type.java_imports)
        else:
            self.java_type = java_class_name(statement.arg)
            # add type definition
            self.top().add_typedef(self.java_type, self)
            self.java_imports.add_import(self.package(), self.java_type)


class Leaf(Typonder, yang='leaf'):
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
        # The target is defined in the module tree but might not be for
        # unused groupings.
        if hasattr(type_spec, 'i_target_node'):
            self.group = 'ref'
            self.reference = Leaf(type_spec.i_target_node, self)
            self.java_type = self.reference.java_type
            self.java_imports.merge(self.reference.java_imports)


class LeafList(Typonder, yang='leaf-list'):
    """
    Wrapper class for leaf list statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        self.java_imports.add_import(
            JAVA_LIST_IMPORTS[0], JAVA_LIST_IMPORTS[1])
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
            if stmt.keyword == 'uses':
                # class name for the import
                class_name = java_class_name(stmt.i_grouping.arg)
                # add the grouping to the list of super classes
                self.uses[class_name] = Grouping(stmt.i_grouping, self)
                self.top().add_class(class_name, self.uses[class_name])
                continue

            # find a node wrapper for supported variable types
            child_wrapper = self.WOOL.get(stmt.keyword)
            if not child_wrapper:
                logging.debug("No wrapper for yang type: %s (%s)" %
                              (stmt.keyword, stmt.arg))
                continue

            result = child_wrapper(stmt, self)
            result.name = stmt.arg
            # remove leading underscores from the name
            java_name = re.sub(r'^_', '', stmt.arg)
            java_name = to_camelcase(java_name)
            self.vars[java_name] = result

    @template_var
    def inherited_vars(self):
        """
        Collects a dictionary of inherited variables that are needed for
        super calls.
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

    @template_var
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
                imports.add_import(JAVA_LIST_INSTANCE_IMPORTS[0],
                                   JAVA_LIST_INSTANCE_IMPORTS[1])
                break
        return imports.get_imports()


class Grouping(Grouponder, yang='grouping'):
    """
    Wrapper class for grouping statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # own Java type name
        self.java_type = java_class_name(statement.arg)
        self.java_imports = ImportDict()
        self.java_imports.add_import(self.package(), self.java_type)
        # add 'case' object as variable when choice substatement exists in
        # grouping
        for sub_st in statement.substmts:
            if sub_st.keyword == 'choice':
                for case in sub_st.substmts:
                    if case.keyword == 'case':
                        java_name = to_camelcase(re.sub(r'^_', '', case.arg))
                        var = Case(case, self)
                        var.name = case.arg
                        self.vars[java_name] = var

    @template_var
    def type(self):
        # FIXME: needs fixing for more than one uses
        if not self.vars:
            if len(self.uses) == 1:
                return next(self.uses.keys())
        else:
            return None

    @template_var
    def inheritance_imports(self):
        """
        :return: Imports needed if inheriting from this class.
        """
        return self.java_imports

    @template_var
    def member_imports(self):
        return self.java_imports


class Container(Grouponder, yang='container'):
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
        # containers that just import a grouping don't need a new class
        # -> variable
        elif len(self.uses) == 1 and len(self.vars) == 0:
            class_item = next(iter(self.uses.values()))
            self.java_type = class_item.java_type
            self.java_imports = class_item.member_imports()
        else:
            # process exception when statement has i_children but no variables
            if len(statement.i_children) > 0 and len(self.vars) == 0:
                # adding variables to container class class
                for child in self.children.values():
                    if child.statement.keyword in [
                            'container', 'grouping', 'list', 'leaf-list',
                    ]:
                        child.name = child.statement.arg
                        java_name = to_camelcase(child.name)
                        self.vars[java_name] = child
            self.java_type = java_class_name(statement.arg)
            self.top().add_class(self.java_type, self)
            self.java_imports.add_import(self.package(), self.java_type)

    @template_var
    def member_imports(self):
        """
        :return: imports needed if this class is a member
        """
        return self.java_imports


class List(Grouponder, yang='list'):
    """
    Wrapper class for list statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.group = 'list'
        self.java_imports = ImportDict()
        self.java_imports.add_import(JAVA_LIST_IMPORTS[0],
                                     JAVA_LIST_IMPORTS[1])
        # check if a super class exists and assign type
        if self.uses:
            # multiple inheritance is not supported in Java:
            # importing all variables
            if len(self.uses) > 1:
                for use in self.uses.values():
                    for child in use.children.values():
                        child.name = child.statement.arg
                        java_name = to_camelcase(child.statement.arg)
                        self.vars[java_name] = child
            # only one super class -> assign type
            else:
                self.type = next(iter(self.uses.values()))
                self.java_imports.merge(self.type.inheritance_imports())
        # check for any other children not already in the variable list and
        # add them
        # FIXME: the 'if' might not work correctly
        # for child_wr in self.children.values():
        #     if child_wr not in self.vars.values():
        #         child_wr.name = child_wr.statement.arg
        #         java_name = to_camelcase(child_wr.statement.arg)
        #         self.vars[java_name] = child_wr
        # if new variables are defined in the list, a helper class is needed
        # FIXME: the commented code (previous fixme) breaks this check
        if self.children and 0 < len(self.vars):
            self.element_type = (java_class_name(statement.arg) +
                                 JAVA_LIST_CLASS_APPENDIX)
            self.top().add_class(self.element_type, self)
            self.java_type = 'List<%s>' % self.element_type
            self.java_imports.add_import(self.package(), self.element_type)
        else:
            # if a type is defined use it
            if hasattr(self, 'type') and hasattr(self.type, 'java_type'):
                self.element_type = self.type.java_type
                self.java_type = 'List<%s>' % self.type.java_type
            # unknown list elements
            else:
                self.java_type = 'List'
        # collect list of keys
        self.keys = [to_camelcase(key.arg)
                     for key in getattr(statement, 'i_key', ())]


class Choice(Grouponder, yang='choice'):

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        # self.java_imports = ImportDict()
        # #add individual class for each case statement
        # for child in self.children.values():
        #     self.top().add_class(child.java_type, child)
        #     self.java_imports.add_import(child.package(), child.java_type)


class Case(Grouponder, yang='case'):

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.java_imports = ImportDict()
        self.java_type = java_class_name(self.statement.arg) + 'CaseType'
        self.top().add_class(self.java_type, self)
        self.java_imports.add_import(self.package(), self.java_type)


class Input(Grouponder, yang='input'):
    """
    Parser for input nodes.
    """


class Output(Grouponder, yang='output'):
    """
    Parser for output nodes.
    """


class RPC(NodeWrapper, yang='rpc'):
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
