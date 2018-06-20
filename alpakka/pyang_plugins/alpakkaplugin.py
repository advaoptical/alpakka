import logging
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
        fmts['alpakkaplugin'] = self

    def add_opts(self, optparser):
        """
        Add akka specific options to the pyang CLI.
        :param optparser: the option parser
        """
        options = [
            optparse.make_option(
                "-w", "--wool", action="store", dest="wool",
                help="The Wool to use for knitting the code"
            ),
            optparse.make_option(
                "--output-path", dest="akka_output", action="store",
                help="output path for the generated classes"
            ),
            optparse.make_option(
                "-i", "--interactive", action="store_true", dest="interactive",
                default=False,
                help="run alpakka in interactive mode by starting an IPython "
                     "shell before template generation"
            ),
            optparse.make_option(
                "--configuration-file-location", action="store",
                dest="config_file", help="path for the wool configuration file"
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
        :return:
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
            logging.info("Wrapping module %s (%s)",
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
                render_template=self.render_template,
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
        self.wool = ctx.opts.wool and WOOLS[ctx.opts.wool] or WOOLS.default
        # set output path
        if ctx.opts.akka_output:
            self.wool.output_path = ctx.opts.akka_output
        # pasing from the wool specific options and configuration parameters
        # is implemented inside the specific wool and can be wool specific
        self.wool.parse_config(self.wool, ctx.opts.config_file)

    def render_template(self, template_name, context):
        """
        Methode which is only needed as part of the interactive mode of the
        alpakka plugin
        :param template_name:
        :param context:
        :return:
        """
        template = self.env.get_template(template_name)
        return template.render(context)
