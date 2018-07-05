from pkg_resources import iter_entry_points
from pprint import pformat

from .default_wool import Wool
from alpakka.logger import LOGGER

__all__ = ['Wool', 'WoolsRegistry']


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

    def register(self, wool):
        """
        Registers the wool together with its python package

        :param wool: the wool
        """
        self.wools[wool.package] = wool
        LOGGER.info("Registered {!r}".format(wool))

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
