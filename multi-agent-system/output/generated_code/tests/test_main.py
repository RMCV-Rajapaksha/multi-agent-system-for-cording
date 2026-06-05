import pytest
from app.main import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_hello_returns_200(client):
    res = client.get('/')
    assert res.status_code == 200
