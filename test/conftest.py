import pytest
import pyang
from path import Path

"""
    Pytest fixture statement, works like a global Variable for the test
    Session. Provides a fixed baseline upon which tests can reliably and
    repeatedly be executed.
    In this file should only statements be defined which are used in multiple
    tests and for the testing of different modules.
"""


@pytest.fixture(scope='session')
def yang_module_name():
    """
    Fixture statement to define the name of reference yang input file and the
    expected yang module which will be processed for testing purposes

    :return: name of the yang module
    """
    return 'virtual-topology-api'


@pytest.fixture(scope='session')
def pyang_plugin_name():
    """
    Fixture statement which returns the name of the pyang plugin which will
    be used
    during the test session

    :return: name of the pyang plugin
    """
    return 'akka'


@pytest.fixture(scope='session')
def yang_module(yang_module_name, yang_context):
    """
    Fixture statement to generate a pyang representation of a yang_module which
    should be used for testing.
    The functionality of the statement is the following, use the pyang
    context generated at the yang_context() function. Afterwards the module
    under test is added to the context.

    :param yang_module_name:    name of the module under test
    :param yang_context:        test context
    :return:                    the module instance
    """

    path = Path(__file__).dirname() / yang_module_name + '.yang'

    module = yang_context.add_module(path, path.text())

    return module


@pytest.fixture(scope='session')
def yang_context():
    """
    Fixture statement to generate the pyang context for test purposes. A
    context is a module which encapsulates the parsing session.

    :return: pyang context object
    """
    repo = pyang.FileRepository(".")

    ctx = pyang.Context(repo)

    return ctx


@pytest.fixture(scope='session')
def yang_query():
    def query(statement, yang_type):
        node_list = set(getattr(statement, 'i_children', ()))
        node_list.intersection_update(getattr(statement, 'substmts', ()))
        for stmt in node_list:
            if stmt.keyword == yang_type:
                yield stmt
            yield from query(stmt, yang_type)

    return query
