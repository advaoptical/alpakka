from alpakka import WOOLS
from alpakka.wrapper import wrap_module
from alpakka.wrapper.nodewrapper import Module


def test_wrap_module(yang_module):
    """
    Test function to test the correct wrapping of a module statement

    :param yang_module:         python representation of a yang module generated with pyang (see conftest.py)
    :return:                    no return value implemented
    """
    wrapped_module = wrap_module(yang_module)
    assert isinstance(wrapped_module, Module)

    # check the mandatory fields of an module
    assert wrapped_module.yang_name() == yang_module.arg
    assert wrapped_module.yang_type() == yang_module.keyword
    assert (wrapped_module.description ==
            yang_module.search_one('description').arg)


# class TestModule:
#
#     def test_all_nodes(self, yang_module, yang_query):
#         wrapped_module = wrap_module(yang_module)
#         all_nodes = wrapped_module.all_nodes
#         assert 'module' not in all_nodes
#         for yang_type in WOOLS.default._yang_wrappers:
#             if yang_type == 'some-node':
#                 # remove clutter created by doctests
#                 continue
#             if yang_type == 'module':
#                 continue
#
#             all_statements = [node.statement
#                               for node in all_nodes[yang_type].values()]
#             assert all_statements == list(yang_query(yang_module, yang_type))



# class TestContainer:
#
#     def test_wrapping_container(yang_module):
#         """
#         Test function to test the correct wrapping of all container statements attached to the yang module under test
#
#         :param yang_module:         python representation of a yang module generated with pyang (see conftest.py)
#         :return:
#         """
#         wrapped_module = wrap_module(yang_module)