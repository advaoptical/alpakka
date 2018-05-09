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
        self.prefix = ""
        self.output_path = ""
        # prepare environment
        self.env = Environment(loader=PackageLoader('alpakka'))
        # add filters to environment
        self.env.filters['firstupper'] = firstupper
        self.env.filters['firstlower'] = firstlower
        self.env.filters['javadefault'] = java_default

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
                "--akka-output-path", dest="akka_output", action="store",
                help="output path for the generated classes"
            ),
            optparse.make_option(
                "--akka-package-prefix", dest="akka_prefix", action="store",
                help="package prefix to be prepended to the generated classes"
            ),
            optparse.make_option(
                "--akka-beans-only", action="store_true", dest="beans_only",
                default=False,
                help="create just the beans without the akka classes"
            ),
            optparse.make_option(
                "-i", "--interactive", action="store_true", dest="interactive",
                default=False,
                help="run alpakka in interactive mode by starting an IPython "
                     "shell before template generation"
            ),
            optparse.make_option(
                "--java-interface-levels", action="store", dest="iface_levels",
                type="int", default=2,
                help="choose the number of levels of the tree that are covered "
                     "by methods in the generated interface before switching "
                     "to reflection "
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
        # for module in wrapped_modules.values():
        #     for name, child in set(module.classes.items()):
        #         if child.statement.i_orig_module.arg != module.yang_module():
        #             if name in wrapped_modules[child.statement.i_orig_module.arg].classes:
        #                 module.classes.pop(name)
        #             else:
        #                 wrapped_modules[child.statement.i_orig_module.arg].classes[name] = child
        #                 module.classes.pop(name)

        if ctx.opts.interactive:
            start_ipython([], user_ns=dict(
                ((module.statement.arg.replace('-', '_'), module)
                 for module in wrapped_modules.values()),
                alpakka=alpakka,
                render_template=self.render_template,
            ))
        else:
            for module in wrapped_modules.values():
                module.generate_classes()
            #self.wool.generate_commons(wrapped_modules)

    def get_options(self, ctx):
        """
        Extract option parameters from the context.
        :param ctx: the context
        """
        self.wool = ctx.opts.wool and WOOLS[ctx.opts.wool] or WOOLS.default
        # set package prefix
        if ctx.opts.akka_prefix:
            self.wool.prefix = ctx.opts.akka_prefix
        # set output path
        if ctx.opts.akka_output:
            self.wool.output_path = ctx.opts.akka_output
        self.wool.beans_only = ctx.opts.beans_only
        self.wool.iface_levels = ctx.opts.iface_levels

    def render_template(self, template_name, context):
        template = self.env.get_template(template_name)
        return template.render(context)