"""Real Ollama smoke test; uses a temporary corpus, never modifies your library."""
import json
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def main():
    configured = Settings.load()
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(Path(directory), configured.ollama_url, configured.chat_model,
                            configured.embed_model, configured.min_score)
        with TestClient(create_app(settings)) as client:
            status = client.get('/api/status').json()
            print('Ollama:', status['ollama'], '| model:', settings.chat_model)
            assert status['ollama'] == 'ready', status
            headers = {'X-Local-Token': status['token']}
            text = ('Runbook proiect Atlas: namespace-ul de productie este atlas-prod. '
                    'Deployment-ul foloseste ArgoCD. Accesul la retea este restrictionat prin NetworkPolicy. '
                    'Orice release necesita aprobarea echipei de platforma.')
            result = client.post('/api/documents', headers=headers,
                                 files={'file': ('atlas-runbook.txt', text.encode())})
            assert result.status_code == 202, result.text
            deadline = time.monotonic() + 300
            while True:
                job = next(j for j in client.get('/api/imports').json() if j['id'] == result.json()['job_id'])
                if job['state'] == 'completed':
                    break
                assert job['state'] != 'failed', job
                assert time.monotonic() < deadline, 'Import timed out'
                time.sleep(0.1)
            reply = client.post('/api/chat', headers=headers,
                                json={'question': 'Care este namespace-ul de productie al proiectului Atlas?'})
            assert reply.status_code == 200, reply.text
            body = reply.json()
            assert body['sources'], body
            assert 'atlas-prod' in body['answer'], body
            assert body['citations_valid'], body
            print(json.dumps(body, ensure_ascii=True, indent=2))
            assert client.get('/').status_code == 200
            print('PASS: real ingestion, retrieval, generation, citations, HTTP UI.')


if __name__ == '__main__':
    main()
