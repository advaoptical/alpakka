from alpakka.logger import LOGGER
import optparse
from pyang import plugin

from IPython import start_ipython

import alpakka
from alpakka import WOOLS
from alpakka.wrapper import wrap_module

default_values = {
    'int': 0,
    'boolean': 'false'
}


def pyang_plugin_init():
    """
    Called by pyang plugin framework at to initialize the plugin.
    :return:
    """
    plugin.register_plugin(AlpakkaPlugin())


class AlpakkaPlugin(plugin.PyangPlugin):
    """
    Plugin to convert a yang model to code stubs.
    """

    def __init__(self):
        super().__init__()

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['alpakka'] = self

    def add_opts(self, optparser):
        """
        Add akka specific options to the pyang CLI.
        :param optparser: the option parser
        """
        options = [
            optparse.make_option(
                "-w", "--wool", action="store", dest="wool",
                help="wool used for knitting the code. Specifies the wool "
                     "required for the target programming language and "
                     "framework."
            ),
            optparse.make_option(
                "--output-path", dest="output", action="store",
                help="specifies the root directory for the code generation"
            ),
            optparse.make_option(
                "-i", "--interactive", action="store_true", dest="interactive",
                default=False,
                help="run alpakka in interactive mode by starting an IPython "
                     "shell before template generation"
            ),
            optparse.make_option(
                "--configuration-file-location", action="store",
                dest="config_file", help="path of the wool configuration file"
            )
        ]
        group = optparser.add_option_group("Akka output specific options")
        group.add_options(options)

    def emit(self, ctx, modules, writef):
        """
        Method which is called by pyang after the parsing and validation is
        finished, this method initiates the output conversion
        :param ctx:
        :param modules: Array of statement objects representing all modules
        :param writef:
        """
        self.get_options(ctx)
        unique_modules = set()
        # collect set of unique modules, avoid wrapping the same one
        # multiple times
        for module in modules:
            for module_details, context_module in module.i_ctx.modules.items():
                unique_modules.add(context_module)
        # wrap unique modules
        wrapped_modules = dict()
        for module in unique_modules:
            LOGGER.info("Wrapping module %s (%s)",
                        module.arg, module.i_latest_revision)
            # wrap module statement
            wrapped_module = wrap_module(module, wool=self.wool)
            wrapped_modules[wrapped_module.yang_module()] = wrapped_module

        # due to the wrapping process statements which are used multiple times
        # in different modules might be wrapped multiple times. To avoid
        # multiple output generations the data structure is traversed and all
        # duplicates, in modules which are not the module which was originally
        # implementing the statement, are deleted.
        # Is implemented inside the used wool and can be wool specific
        for module in wrapped_modules.values():
            self.wool.wrapping_postprocessing(module, wrapped_modules)

        if ctx.opts.interactive:
            start_ipython([], user_ns=dict(
                ((module.statement.arg.replace('-', '_'), module)
                 for module in wrapped_modules.values()),
                alpakka=alpakka,
            ))
        else:
            # output generation is performed per parsed module and is
            # implemented inside the used wool. Can be wool specific
            for wrapped_module in wrapped_modules.values():
                self.wool.generate_output(wrapped_module)

    def get_options(self, ctx):
        """
        Extract option parameters from the context.
        :param ctx: the context
        """
        # parsing of options which are general for the alpakkaplugin and not
        # wool specific
        self.wool = WOOLS[ctx.opts.wool] or WOOLS.default
        # set output path
        self.wool.output_path = ctx.opts.output or ""
        # pasing from the wool specific options and configuration parameters
        # is implemented inside the specific wool and can be wool specific
        self.wool.parse_config(ctx.opts.config_file)
