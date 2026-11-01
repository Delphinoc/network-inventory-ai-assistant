import pytest

from nia.db import connect
from nia.retriever import Retriever
from nia.tools import Toolbox


@pytest.fixture(scope="session")
def con():
    return connect()


@pytest.fixture(scope="session")
def toolbox(con):
    return Toolbox(con, Retriever())
