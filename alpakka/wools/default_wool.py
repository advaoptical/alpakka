from alpakka.logger import LOGGER
from functools import lru_cache
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
        self.data_type_mappings = Types(type_patterns or {})
        self.yang_wrappers = parent and dict(parent.yang_wrappers) or {}
        LOGGER.debug("Wool created: %s" % name)

    def id(self):
        """
        :return: the wool's identifier (lower case name)
        """
        return self.name.lower()

    @lru_cache()
    def _woolify(self, wrapcls):
        """
        Woolify the given :class:`alpakka.NodeWrapper`-derived `wrapcls`.

        Dynamically derive a new class from `wrapcls` and all ``.mixins``
        for this Wool and its parents defined by `wrapcls` and all its bases

        Finally add a ``.WOOL`` reference to the new class

        :return: A cached woolified class derived from `wrapcls`
        """
        # Can't be imported at module level due to unsatisfied circular
        # dependencies
        import alpakka.wrapper

        mixins = []
        for base in wrapcls.mro():
            if issubclass(base, alpakka.wrapper.NodeWrapper):
                wool = self
                while wool is not None:
                    for mixincls in base.mixins.get(wool.package, ()):
                        mixins.append(mixincls)
                    wool = wool.parent

        bases = (*mixins, wrapcls)
        # We also need a new metaclass derived from all the metaclasses of the
        # bases, but w/o duplicates or metaclasses that are superclasses of
        # others in the list of base metaclasses
        metabases = []
        for meta in map(type, bases):
            metabases = [
                mb for mb in metabases
                if not issubclass(meta, mb)]
            if meta not in metabases:
                metabases.append(meta)

        class Meta(*metabases):
            pass

        return Meta(wrapcls.__name__, (*mixins, wrapcls), {
            '__module__': "alpakka.WOOLS['{}']".format(self.name),
            'WOOL': self})

    def __getitem__(self, name):
        """
        Get the Woolified YANG node wrapper class for YANG statement `name`.

        See :meth:`._woolify` for Woolification details
        """
        return self._woolify(self.yang_wrappers[name])

    def get(self, name):
        """
        Get the Woolified YANG node wrapper class for YANG statement `name`.

        Returns ``None`` if no wrapper can be found instead of raising an
        exception

        See :meth:`._woolify` for Woolification details
        """
        wrapcls = self.yang_wrappers.get(name)
        if wrapcls is not None:
            return self._woolify(wrapcls)

    def __getattr__(self, name):
        """
        Get the Woolified YANG node wrapper class with given `name`.

        See :meth:`._woolify` for Woolification details
        """
        for wrapcls in self.yang_wrappers.values():
            if wrapcls.__name__ == name:
                return self._woolify(wrapcls)

        raise AttributeError(name)

    def __dir__(self):
        """
        Add all YANG node wrapper class names of this Wool.

        For use with :meth:`.__getattr__`
        """
        return (*super().__dir__(),
                *(wrapcls.__name__ for wrapcls in
                  getattr(self, 'yang_wrappers', dict()).values()))

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
