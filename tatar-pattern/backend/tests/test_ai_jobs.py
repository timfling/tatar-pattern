"""Legacy AI requests are explicitly retired; stored history is tested in test_ai_mvp."""
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app


def test_old_ai_submission_is_rejected_without_ignoring_selection(prepared):
    with TestClient(create_app(prepared[0])) as client:
        client.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':'persistent job password'})
        old={'mode':'ai','selections':{'style':'heritage','composition':'medallion','motifs':['tulip'],'palette':'emerald','usage':'web'}}
        response=client.post('/api/generations',json=old)
        assert response.status_code==422
        assert response.json()['error']['code']=='AI_SELECTIONS_UNSUPPORTED'
        assert not client.get('/api/capabilities').json()['modes']['ai']['available']
