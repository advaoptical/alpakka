__all__ = ['WOOLS', 'LOGGER', 'NodeWrapper', 'Wool', 'run']

from alpakka.logger import LOGGER
from alpakka.wools import WoolsRegistry, Wool

#: The central Wool registry. ``WOOLS.default`` is the basic Wool. All Wool
#  plugins go into ``WOOLS[<plugin name>]``
WOOLS = WoolsRegistry()

# implicitly loads default Wool
from alpakka.wrapper import NodeWrapper  # Ignore PycodestyleBear (E402)


def run():
    from . import __main__  # which exec()s the pyang script

    # then manually run the pyang script's run function
    # which is only run automatically if __file__ == '__main__'
    # but now __main__.__file__ == 'alpakka.__main__'
    __main__.run()
