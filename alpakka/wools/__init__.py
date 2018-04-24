from pprint import pformat

from pkg_resources import iter_entry_points

from alpakka.logger import LOGGER

__all__ = ['Wool', 'register']


def load_from_entry_points():
    """
    Auto-load all Wool packages which are defined as ``'alpakka_wools'``
    entry-points in their distribution's ``setuptools.setup()``, which looks
    like::

       setup(
           entry_points={
               'alpakka_wools': ['name=package'],
               ...},
           ...)

    To be actually registered as Wools, those packages must of course
    additionally call :func:`alpakka.register_wool`
    """
    for woolpoint in iter_entry_points('alpakka_wools'):
        woolpoint.load()


def register(registry, name, package, parent=None, data_type_patterns=None):
    """
    Creates a new :class:`alpakka.Wool` instance and adds it to the
    given `registry`

    :param registry: The :class:`alpakka.wools.WoolsRegistry` instance to use
    :param name:     The Wool's name
    :param package:  The Wool's fully-qualified python package name
    :param parent:   The optional case-insentitive name of an already
                     registered parent wool Which is further customized by
                     this Wool
    """
    if parent:
        parentwool = registry[parent.lower()]
    else:
        parentwool = registry.default

    wool = Wool(name, package, parent=parentwool,
                data_type_patterns=data_type_patterns)
    registry.register(package, wool)

    LOGGER.info("Registered {!r}".format(wool))
    return wool


class Wool(object):
    """
    The wool handler that stores the wool's name, its python package name,
    and an optional parent :class:`Wool` instance

    For case-insentitive lookups, a normalized identification name for the
    wool is created by lowering the wool's name
    """

    def __init__(self, name, package, parent=None, data_type_patterns=None):
        """
        :param name:    The wool's name
        :param package: The wool's fully-qualified python package name
        :param parent:  The optional :class:`Wool` instance of a parent wool
                        which is further customized by this wool
        """
        self.name = name
        self.package = package
        self.parent = parent
        self.prefix = ''
        self.output_path = ''
        self.beans_only = False

        self._data_type_patterns = (parent and
                                    dict(parent._data_type_patterns) or {})
        if data_type_patterns is not None:
            self._data_type_patterns.update(data_type_patterns)

        self._yang_wrappers = parent and dict(parent._yang_wrappers) or {}

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
        return self._selfify(self._yang_wrappers[name])

    def get(self, name):
        """
        Get the Wool's YANG node wrapper class for given YANG statement
        `name`, returning ``None`` if it can't be found, instead of raising an
        exception

        If the class comes from a parent Wool and therefore doesn't have this
        Wool as ``.WOOL`` reference, the ``.WOOL`` will be overridden
        """
        wrapcls = self._yang_wrappers.get(name)
        if wrapcls is not None:
            return self._selfify(wrapcls)

    def __getattr__(self, name):
        """
        Get the Wool's YANG node wrapper class that has given class `name`,
        instead of YANG statement name

        If the class comes from a parent Wool and therefore doesn't have this
        Wool as ``.WOOL`` reference, the ``.WOOL`` will be overridden
        """
        for wrapcls in self._yang_wrappers.values():
            if wrapcls.__name__ == name:
                return self._selfify(wrapcls)

        raise AttributeError(name)

    def __dir__(self):
        """
        Extend basic ``__dir__`` with all YANG node wrapper class names of
        this Wool, for use with :meth:`.__getattr__`
        """
        return super().__dir__() + [wrapcls.__name__ for wrapcls in
                                    self._yang_wrappers.values()]

    def __repr__(self):
        """
        Create a representation in instantiation code style
        """
        return "{}({!r}, {!r}, parent={!r})".format(
            type(self).__qualname__, self.name, self.package,
            self.parent and self.parent.name)


class WoolsRegistry:
    """
    The class of the :data:`alpakka.WOOLS` registry

    Actual wool registration is done via :func:`alpakka.register_wool`. See
    the latter for more information about that process. It also explains how
    to access the registered :class:`alpakka.Wool` instances later

    The manager registers every wool with the normalized all-lowercased wool
    name (wool id) as plugin name
    """

    def __init__(self):
        self.wools = dict()

    def register(self, package, wool):
        """
        Registers the wool together with its python package
        :param package: the wool's python package
        :param wool: the wool
        """
        self.wools[package] = wool

    def items(self):
        """
        Iterates ``(<wool id>, <alpakka.Wool instance>)`` pairs
        """
        for wool in self.wools.items():
            yield wool.id(), wool

    def names(self):
        """
        Iterates names of registered wools
        """
        for wool in self.wools.items():
            yield wool.name

    def packages(self):
        """
        Iterates python package names of registered wools
        """
        yield from self.wools.keys()

    def __contains__(self, name_or_package):
        """
        Checks if given string is either a name or a python package name of
        any registered wool, whereby name lookup is case-insensitive
        """
        for package, wool in self.wools.items():
            if name_or_package == package or (
                    name_or_package.lower() == wool.id()):
                return True

        return False

    def __getitem__(self, name_or_package):
        """
        Get a registered :class:`alpakka.Wool` instance by either its name or
        its python package name, whereby name lookup is case-insensitive
        """
        wool = self.wools.get(name_or_package)
        if wool:
            return wool

        for i_wool in self.wools.values():
            if i_wool.id() == name_or_package.lower():
                return i_wool

        raise KeyError(name_or_package)

    def __repr__(self):
        """
        Pretty-print a ``dict``-representation of the registered wools with
        their normalized identification names as keys
        """
        return pformat(dict(self.items()))
