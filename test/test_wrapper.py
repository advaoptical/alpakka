from alpakka.wrapper import wrap_module
from alpakka.wrapper.grouponder import Module
from collections import OrderedDict


def test_wrap_module(yang_module):
    """
    Test function to test the correct wrapping of a module statement

    :param yang_module:         python representation of a yang module
                                generated with pyang (see conftest.py)
    :return:                    no return value implemented
    """
    wrapped_module = wrap_module(yang_module)
    assert isinstance(wrapped_module, Module)

    # check the mandatory fields of an module
    assert wrapped_module.yang_name() == yang_module.arg
    assert wrapped_module.yang_type() == yang_module.keyword
    assert (wrapped_module.description ==
            yang_module.search_one('description').arg)


class TestModule:

    def test_all_nodes(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert 'module' not in wrapped_module.all_nodes
        assert {'topologies', 'endpoints'} == {
            i.rsplit('/', 1)[1] for i in
            wrapped_module.all_nodes['container'].keys()}
        assert {'intent-group'} == {
            i.rsplit('/', 1)[1] for i in
            wrapped_module.all_nodes['grouping'].keys()}
        assert {'endpoints'} == {
            i.rsplit('/', 1)[1] for i in
            wrapped_module.all_nodes['leaf-list'].keys()}
        assert {
            'intents', 'installed-topologies', 'assigned-endpoints',
            'intents'} == {
            i.rsplit('/', 1)[1] for i in
            wrapped_module.all_nodes['list'].keys()}
        assert {
            'endpoint-identifier', 'intent-identifier',
            'topology-identifier', 'bit-rate', 'disjoint'} == {
            i.rsplit('/', 1)[1] for i in
            wrapped_module.all_nodes['typedef'].keys()}
        assert {
            'endpoint-id', 'protection', 'minimum-paths',
            'flexible-bandwidth', 'dedicated-bandwidth',
            'intent-id', 'disjoint-paths', 'satisfied',
            'maximum-active-connections',
            'topology-id'} == {
            i.rsplit('/', 1)[1] for i in
            wrapped_module.all_nodes['leaf'].keys()}

    def test_yang_type(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert 'module' == wrapped_module.yang_type()

    def test_yang_name(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert 'virtual-topology-api' == wrapped_module.yang_name()

    def test_statement(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert yang_module == wrapped_module.statement

    def test_parent(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert None is wrapped_module.parent

    def test_description(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert yang_module.search_one('description').arg == \
            wrapped_module.description

    def test_children(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert set([i.arg for i in yang_module.i_children]) == set(
            wrapped_module.children.keys())

    def test_derived_types(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert yang_module.i_typedefs.keys() == \
            wrapped_module.derived_types.keys()

    def test_uses(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert OrderedDict() == \
            wrapped_module.uses

    def test_all_children(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert wrapped_module.children == wrapped_module.all_children()

    def test_top(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        assert wrapped_module == wrapped_module.top()


class TestContainer:

    def test_parent(self, yang_module):
        """
        Test function to test the correct wrapping of all container statements
        attached to the yang module under test

        :param yang_module:         python representation of a yang module
                                    generated with pyang (see conftest.py)
        :return:
        """
        wrapped_module = wrap_module(yang_module)
        wrapped_container = wrapped_module.topologies

        assert wrapped_module == wrapped_container.parent

    def test_children(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        wrapped_container = wrapped_module.topologies

        assert sorted(['installed-topologies']) == sorted(wrapped_container.
                                                          children)

    def test_config(self, yang_module):
        wrapped_module = wrap_module(yang_module)
        wrapped_container = wrapped_module.topologies

        assert True is wrapped_container.config
