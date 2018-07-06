import re
import pyang.types


class Types:
    """
    Class storing mappings from yang data types to language specific data
    types.
    """

    def __init__(self, patterns):
        """
        Initialize types with a set of tuples, which comprise a regular
        expression and a corresponding type.

        :param patterns: A set of tuples storing patterns and types
        """
        self.patterns = patterns

    def __getitem__(self, yang_type):
        for yang_pattern, data_type in self.patterns:
            if re.match(yang_pattern, yang_type):
                return data_type
        if pyang.types.is_base_type(yang_type):
            return yang_type


class Wool(object):
    """
    The wool handler that stores the wool's name, its python package name,
    and an optional parent :class:`Wool` instance

    For case-insentitive lookups, a normalized identification name for the
    wool is created by lowering the wool's name
    """

    def __init__(self, name, package, parent=None, type_patterns=None):
        """
        :param name:    The wool's name
        :param package: The wool's fully-qualified python package name
        :param parent:  The optional :class:`Wool` instance of a parent wool
                        which is further customized by this wool
        """
        self.name = name
        self.package = package
        self.parent = parent
        self.output_path = ''
        self.config = {}
        self.data_type_mappings = Types(type_patterns)
        self.yang_wrappers = parent and dict(parent.yang_wrappers) or {}

    def id(self):
        """
        :return: the wool's identifier (lower case name)
        """
        return self.name.lower()

    def _selfify(self, wrapcls):
        """
        Check if ``.WOOL`` reference of given
        :class:`alpakka.NodeWrapper`-derived `wrapcls` is `self`, and if not,
        override the ``.WOOL`` reference

        :return: given `wrapcls` with correct ``.WOOL`` reference
        """
        if wrapcls.WOOL is not self:
            wrapcls.WOOL = self
        return wrapcls

    def __getitem__(self, name):
        """
        Get the Wool's YANG node wrapper class for given YANG statement `name`

        If the class comes from a parent Wool and therefore doesn't have this
        Wool as ``.WOOL`` reference, the ``.WOOL`` will be overridden
        """
        return self._selfify(self.yang_wrappers[name])

    def get(self, name):
        """
        Get the Wool's YANG node wrapper class for given YANG statement
        `name`, returning ``None`` if it can't be found, instead of raising an
        exception

        If the class comes from a parent Wool and therefore doesn't have this
        Wool as ``.WOOL`` reference, the ``.WOOL`` will be overridden
        """
        wrapcls = self.yang_wrappers.get(name)
        if wrapcls is not None:
            return self._selfify(wrapcls)

    def __getattr__(self, name):
        """
        Get the Wool's YANG node wrapper class that has given class `name`,
        instead of YANG statement name

        If the class comes from a parent Wool and therefore doesn't have this
        Wool as ``.WOOL`` reference, the ``.WOOL`` will be overridden
        """
        for wrapcls in self.yang_wrappers.values():
            if wrapcls.__name__ == name:
                return self._selfify(wrapcls)

        raise AttributeError(name)

    def __dir__(self):
        """
        Extend basic ``__dir__`` with all YANG node wrapper class names of
        this Wool, for use with :meth:`.__getattr__`
        """
        return super().__dir__() + [wrapcls.__name__ for wrapcls in
                                    getattr(self, 'yang_wrappers',
                                            dict()).values()]

    def __repr__(self):
        """
        Create a representation in instantiation code style
        """
        return "{}({!r}, {!r}, parent={!r})".format(
            type(self).__qualname__, self.name, self.package,
            self.parent and self.parent.name)

    def parse_config(self, path):
        """
        Method interface for the wool implementation to handle the wool
        specific configuration and options
        :param path: location of the configuration file
        :return
        """
        raise NotImplementedError

    def generate_output(self, module):
        """
        Method interface for the wool implementation of the output generation
        is implemented as part of the dedicated wool implementation

        :param module: wrapped module for which the output is generated
        :return
        """
        raise NotImplementedError

    def wrapping_postprocessing(self, module, wrapped_modules):
        """
        Method Interface for the duplication detection and the data cleansing
        which can be used and implemented by each wool

        :param wrapped_modules: list of all module statement which are
            processed
        :param module: the module for which the cleansing should be performed
        :return
        """
        raise NotImplementedError
