import sys
import sysconfig

from path import Path

import alpakka.commands
import alpakka.pyang_plugins
import alpakka.wools


# auto-load all Wools which are defined as 'alpakka_wools' entry points in
# their distribution's setuptools.setup()
alpakka.wools.load_from_entry_points()


# Parse command line for pure non-pyang-invoking alpakka command flags
ALPAKKA_COMMAND_ARGS, _ = alpakka.commands.PARSER.parse_known_args()

ALPAKKA_COMMAND = ALPAKKA_COMMAND_ARGS.command
if ALPAKKA_COMMAND:
    sys.exit(ALPAKKA_COMMAND())


# If no pure alpakka command flag was given then invoke pyang...
ALPAKKA_PLUGIN_DIR = Path(alpakka.pyang_plugins.__file__).realpath().dirname()

PYANG_SCRIPT = Path(sysconfig.get_path('scripts')) / 'pyang'


sys.argv += ['--plugindir', ALPAKKA_PLUGIN_DIR, '-f', 'alpakka']
exec(compile(PYANG_SCRIPT.text(), PYANG_SCRIPT, 'exec'))
