from alpakka.wrapper import wrap_module
from alpakka.wrapper.nodewrapper import Module


def test_wrap_module(yang_module):
    """
    Test function to test the wrapper initialization and some of the nodewrapper
    features

    :param yang_module:         python representation of a yang module generated with pyang (see conftest.py)
    :param yang_module_name:    name of the yang module (see conftest.py)
    :return:                    no return value implemented
    """
    wrapped_module = wrap_module(yang_module)
    assert isinstance(wrapped_module, Module)

    # check the mandatory fields of an module
    assert wrapped_module.yang_stmt_name == yang_module.arg
    assert wrapped_module.yang_stmt_type == yang_module.keyword
    assert [wrapped_module.description] == [i.arg for i in yang_module.substmts if i.keyword == 'description']


