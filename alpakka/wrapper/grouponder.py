from alpakka.wrapper.nodewrapper import NodeWrapper
from alpakka.wrapper.nodewrapper import Listonder
from collections import OrderedDict
from alpakka.logger import LOGGER
import alpakka

WOOLS = alpakka.WOOLS


class Grouponder(NodeWrapper):
    """
    Base class for node wrappers that group variables.
    """

    def __init__(self, statement, parent):
        """
        Constructor for a grouponder which extracts all statements which are
        childes of the current statement

        :param children: all wrapped statements which are children of this
                         statement as list
        :param uses: if the current statement has a uses substmt a Grouping
                     object created and stored in the uses var
        :param is_augmented: identifier to indicate is the current statement
                             augmented by an other module or not
        """
        super().__init__(statement, parent)
        self.uses = OrderedDict()
        self.children = OrderedDict()

        # the following line separates stmts which are imported with 'uses'
        # from normal integrated stmts
        children_list = set(getattr(statement, 'i_children', ()))

        # wrap all children of the node
        for child in children_list:
            child_wrapper = self.WOOL.get(child.keyword)
            if child_wrapper:
                self.children[child.arg] = child_wrapper(child, parent=self)
            else:
                LOGGER.info("No wrapper for yang type: %s (%s)" %
                            (child.keyword, child.arg))

        # find all stmts which are imported with a 'uses' substmt and wrap the
        # Grouping object related to ths uses
        uses_list = set(statement.search('uses'))
        for stmt in uses_list:
            # check is the used grouping already wrapped
            # if so, the wrapped grouping is linked in the 'uses' variable
            # if not a the grouping statement is wrapped
            key = stmt.i_grouping.parent.arg + '/' + stmt.i_grouping.arg
            group = self.top().all_nodes.get('grouping', {}).get(key)
            if group:
                self.uses[group.yang_name()] = group
            else:
                self.uses[stmt.i_grouping.arg] = \
                    self.WOOL['grouping'](stmt.i_grouping, parent=self.top())

        # special handling for augment imports
        # collect all keys of augments

        augmented_keys = []

        for children in set(getattr(statement, 'i_children', ())):
            if hasattr(children, 'i_augment'):
                self.is_augmented = True
                augment_stmt = children.i_augment
                if augment_stmt.parent.arg not in augmented_keys:
                    augmented_keys.append(augment_stmt.parent.arg)
                    # Handling for Groupings which are imported with
                    # a augment statement
                    for grp in set(augment_stmt.search('uses')):
                        key = grp.parent.arg[1:] + '/' + \
                              grp.arg
                        group = self.top().all_nodes.get('grouping', {}). \
                            get(key)
                        if group:
                            self.uses[group.yang_name()] = group
                        else:
                            self.uses[grp.arg] = \
                                self.WOOL['grouping'](grp,
                                                      parent=self.top())

    def __getitem__(self, key):
        """
        Methode, that allows to access of the child elements directly as list
        of the top element
        :param key: name of the child elements which should be accessed
        :return: child object
        """

        return self.children[key]

    def __getattr__(self, name):
        """
        Methode, that allows to access a child element directly due the
        <parent>.<child> syntax

        :param name: name of the child element
        :return: child element object
        """
        if name == 'children':
            raise AttributeError
        key = name.replace('_', '-')
        try:
            return self.children[key]

        except KeyError:
            raise AttributeError("{!r} has no attribute {!r} or child {!r}"
                                 .format(self, name, key))

    def __dir__(self):
        """
        Mathode, that list all child elements as options of the auto completion

        :return: list of elements that are in the children list
        """
        return (*super().__dir__(),
                *(key.replace('-', '_') for key in
                  getattr(self, 'children', dict())))

    def all_children(self):
        """
        Collects a list of all child stmts of the current stmt regardless of
        the kind of implementation (local or import).
        :return: list of stmts
        """
        result = OrderedDict(self.children)
        result.update(self.uses)
        return result


class Module(Grouponder, yang='module'):
    """
    Wrapper class for a module statement.
    """

    def __init__(self, statement, parent=None):
        """
        Constructor for Class objects for module statements

        :param modules: Dictionary of classes of yang statements, where each
        class is a dictionary of all wrapped statements of the current module
        :param derived_types: Dictionary of all type defs which are used inside
        this module
        """
        self.all_nodes = {}
        self.derived_types = OrderedDict()
        super().__init__(statement, parent)
        # if self.statement.search_one('augment'):
        #     container = self.statement.search_one('augment').i_target_node
        #     self.WOOL.get(container.keyword)(container, self)


class Container(Grouponder, yang='container'):
    """
    Wrapper class for container statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Grouping(Grouponder, yang='grouping'):
    """
    Wrapper class for grouping statements.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class List(Grouponder, Listonder, yang='list'):
    """
    Wrapper class for list statements.

    :param keys: the values originally stored in the key substmt of an yang
    list stmt
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.keys = set()
        key_stmt = statement.search_one('key')
        if key_stmt is not None and key_stmt.arg is not None:
            # the key statement contains a space separated list of keys
            for key in key_stmt.arg.split():
                self.keys.add(key)


class Choice(Grouponder, yang='choice'):
    """
    Wrapper class for choice statements

    :param cases: Dictionary of all possible cases for the choice stmt
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        self.cases = OrderedDict()
        for case in self.statement.search('case'):
            self.cases[case.arg] = self.WOOL['case'](case, self)


class Case(Grouponder, yang='case'):
    """
    Wrapper class for case statements
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class RPC(Grouponder, yang='rpc'):
    """
    Parser for RPC nodes.

    :param input: stores the wrapped input statement
    :param output: stores the wrapped output statement
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
        for item in self.statement.i_children:
            if item.keyword == 'input':
                self.input = self.WOOL['input'](item, self)
            elif item.keyword == 'output':
                self.output = self.WOOL['output'](item, self)


class Input(Grouponder, yang='input'):
    """
    Parser for input nodes.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)


class Output(Grouponder, yang='output'):
    """
    Parser for output nodes.
    """

    def __init__(self, statement, parent):
        super().__init__(statement, parent)
