import optparse
import os

from jinja2 import Environment, PackageLoader
from pyang import plugin

from alpakka.wrapper import wrap_module


def firstupper(value):
    """
    Makes the first letter of the value upper case without touching the rest of the string.
    :param value: the string to be processed
    :return: the value with a upper case first letter
    """
    first = value[0] if len(value) > 0 else ''
    remaining = value[1:] if len(value) > 1 else ''
    return first.upper() + remaining


def firstlower(value):
    """
    Makes the first letter of the value lower case without touching the rest of the string.
    :param value: the string to be processed
    :return: the value with a lower case first letter
    """
    first = value[0] if len(value) > 0 else ''
    remaining = value[1:] if len(value) > 1 else ''
    return first.lower() + remaining


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

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['akka'] = self

    def add_opts(self, optparser):
        """
        Add akka specific options to the pyang CLI.
        :param optparser: the option parser
        """
        options = [
            optparse.make_option("--akka-output-path",
                                 dest="akka_output",
                                 action="store",
                                 help="output path for the generated classes"
                                 ),
            optparse.make_option("--akka-package-prefix",
                                 dest="akka_prefix",
                                 action="store",
                                 help="package prefix to be prepended to the generated classes"
                                 )
        ]
        group = optparser.add_option_group("Akka output specific options")
        group.add_options(options)

    def emit(self, ctx, modules, writef):
        self.get_options(ctx)
        for module in modules:
            # wrap module statement
            wrapped_module = wrap_module(module)
            self.generate_classes(wrapped_module)

    def get_options(self, ctx):
        """
        Extract option parameters from the context.
        :param ctx: the context
        """
        # set package prefix
        if ctx.opts.akka_prefix:
            self.prefix = ctx.opts.akka_prefix
        # set output path
        if ctx.opts.akka_output:
            self.output_path = ctx.opts.akka_output

    def generate_classes(self, module):
        full_path = "%s/%s" % (self.output_path, module.subpath())
        # generate enum classes
        self.fill_template('enum_type.jinja', module.enums(), full_path)
        # generate base class extensions
        self.fill_template('class_type.jinja', module.base_extensions(), full_path)
        # generate classes
        self.fill_template('grouping.jinja', module.classes, full_path)
        # generate unions
        self.fill_template('union.jinja', module.unions(), full_path)
        # run only if rpcs are available
        if module.rpcs:
            if_name = '%sInterface' % module.java_name
            rpc_imports = {imp for rpc in module.rpcs.values()
                           if hasattr(rpc, 'imports')
                           for imp in rpc.imports()}
            rpc_dict = {'rpcs': module.rpcs, 'imports': rpc_imports, 'package': module.package()}
            self.fill_template('backend_interface.jinja', {if_name: rpc_dict}, full_path)
            rpc_dict['interface_name'] = if_name
            self.fill_template('backend_impl.jinja',
                               {'%sBackend' % module.java_name: rpc_dict},
                               full_path)
            self.fill_template('routes.jinja', {'%sRoutes' % module.java_name: rpc_dict},
                               full_path)

    def fill_template(self, template_name, description_dict, output_path):
        template = self.env.get_template(template_name)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        for key, context in description_dict.items():
            output = template.render(ctx=context, name=key)
            print(output)
            with open("%s/%s.java" % (output_path, key), 'w') as f:
                f.write(output)
