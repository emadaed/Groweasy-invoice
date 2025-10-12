import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app



import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_index_route(client):
    """Basic smoke test for index route"""
    response = client.get("/")
    print(response.data)  # Debug output
    assert response.status_code == 200
    assert b"DigiReceipt" in response.data
