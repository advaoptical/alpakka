import sys
import sysconfig

import alpakka.pyang_plugins
from path import Path

plugindir = Path(alpakka.pyang_plugins.__file__).realpath().dirname()
sys.argv += ['--plugindir', plugindir, '-f', 'akka']

pyang = Path(sysconfig.get_path('scripts')) / 'pyang'
exec(compile(pyang.text(), pyang, 'exec'))
