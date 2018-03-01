__all__ = ['WOOLS', 'LOGGER', 'NodeWrapper', 'Wool', 'register_wool', 'run']

import alpakka.wools
from alpakka.logger import LOGGER
from alpakka.wools import WoolsRegistry, Wool


#: The central Wool registry. ``WOOLS.default`` is the basic Wool. All Wool
#  plugins go into ``WOOLS[<plugin name>]``
WOOLS = WoolsRegistry()


# implicitly loads default Wool
from alpakka.wrapper import NodeWrapper  # Ignore PycodestyleBear (E402)


def register_wool(name, package, parent=None, data_type_patterns=None):
    return alpakka.wools.register(WOOLS, name, package, parent=parent,
                                  data_type_patterns=data_type_patterns)


# auto-load all Wools which are defined as 'alpakka_wools' entry points in
# their distribution's setuptools.setup()
alpakka.wools.load_from_entry_points()


def run():
    from . import __main__  # which exec()s the pyang script

    # then manually run the pyang script's run function
    # which is only run automatically if __file__ == '__main__'
    # but now __main__.__file__ == 'yang2adonis.__main__'
    __main__.run()
