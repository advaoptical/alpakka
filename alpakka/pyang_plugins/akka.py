import logging
import optparse
import os

from jinja2 import Environment, PackageLoader
from pyang import plugin

from IPython import start_ipython

import alpakka
from alpakka import WOOLS
from alpakka.wrapper import wrap_module


default_values = {
    'int': 0,
    'boolean': 'false'
}


def firstupper(value):
    """
    Makes the first letter of the value upper case without touching
    the rest of the string.
    In case the value starts with an '_' it is removed and the following letter
    is made upper case.

    :param value: the string to be processed
    :return: the value with a upper case first letter

    >>> firstupper('helloworld')
    'Helloworld'
    >>> firstupper('_HelloWorld')
    'HelloWorld'
    """
    value = value.lstrip('_')
    return value and value[0].upper() + value[1:]


def firstlower(value):
    """
    Makes the first letter of the value lower case without touching
    the rest of the string.

    :param value: the string to be processed
    :return: the value with a lower case first letter

    >>> firstlower('HelloWorld')
    'helloWorld'
    """
    return value and value[0].lower() + value[1:]


def java_default(value):
    """
    Maps the java type to the corresponding default value.

    :param value: the java type string
    :return: the default value

    >>> java_default('int')
    0
    >>> java_default('boolean')
    'false'
    >>> java_default('Object')
    'null'
    """
    return default_values.get(value, 'null')


def pyang_plugin_init():
    plugin.register_plugin(AkkaPlugin())


class AkkaPlugin(plugin.PyangPlugin):
    """
    Plugin to convert a yang model to akka code stubs.
    """

    def __init__(self):
        super().__init__()

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['akka'] = self

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

        # delete class duplications
        for module in wrapped_modules.values():
            self.wool.clear_data_structure(wrapped_modules, module)

        if ctx.opts.interactive:
            start_ipython([], user_ns=dict(
                ((module.statement.arg.replace('-', '_'), module)
                 for module in wrapped_modules.values()),
                alpakka=alpakka,
                render_template=self.render_template,
            ))
        else:
            for wrapped_module in wrapped_modules.values():
                self.wool.generate_output(wrapped_module)

    def get_options(self, ctx):
        """
        Extract option parameters from the context.
        :param ctx: the context
        """
        self.wool = ctx.opts.wool and WOOLS[ctx.opts.wool] or WOOLS.default
        # set output path
        if ctx.opts.akka_output:
            self.wool.output_path = ctx.opts.akka_output
        self.wool.parse_config(ctx.opts.config_file)

    def render_template(self, template_name, context):
        template = self.env.get_template(template_name)
        return template.render(context)
