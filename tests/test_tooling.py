import io
import subprocess
import sys
from types import SimpleNamespace

import httpx
import pytest
from dotenv import dotenv_values

from app.config import Settings
from app.rag import Ollama, RagError
from cli import compose, configure_postgres, import_docs, postgres_backup


def test_generated_credentials_are_preserved(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.env').write_text('CHAT_MODEL=existing\n', encoding='utf-8')
    configure_postgres.main()
    first = dotenv_values('.env')
    configure_postgres.main()
    second = dotenv_values('.env')
    assert first == second
    assert first['CHAT_MODEL'] == 'existing'
    assert first['POSTGRES_ADMIN_PASSWORD'] != first['OPSATLAS_DB_PASSWORD']
    assert first['OPSATLAS_DB_PASSWORD'] in first['DATABASE_URL']
    assert first['OPSATLAS_DB_PASSWORD'] not in capsys.readouterr().out


@pytest.mark.parametrize('action,expected', [('start',['up','-d','--build']),('stop',['stop'])])
def test_compose_builds_safe_commands(tmp_path, monkeypatch, action, expected):
    monkeypatch.setattr(compose,'ROOT',tmp_path)
    (tmp_path/'.env').write_text('EXAMPLE=1')
    monkeypatch.delenv('PODMAN_COMPOSE_PROVIDER',raising=False)
    monkeypatch.setattr(compose.shutil,'which',lambda name,**kw: '/tools/'+name if name in {'podman','podman-compose'} else None)
    argv, env = compose.command(action)
    assert argv == ['/tools/podman','compose']+expected
    assert env['PODMAN_COMPOSE_PROVIDER'] == '/tools/podman-compose'
    assert '-v' not in argv
    assert compose.command(action,check=True)[0][-1] == 'version'


def test_compose_missing_configuration_is_actionable(tmp_path,monkeypatch):
    monkeypatch.setattr(compose,'ROOT',tmp_path)
    monkeypatch.delenv('PODMAN_COMPOSE_PROVIDER',raising=False)
    monkeypatch.setattr(compose.shutil,'which',lambda name,**kw: '/tools/'+name)
    with pytest.raises(RuntimeError,match='Missing .env'):
        compose.command('start')


def test_import_cli_dry_run_does_not_create_database(tmp_path,monkeypatch):
    (tmp_path/'note.md').write_text('hello')
    monkeypatch.setattr(sys,'argv',['import_docs','--path',str(tmp_path),'--dry-run'])
    monkeypatch.setattr(import_docs,'create_store',lambda *args: pytest.fail('Dry run must not open database'))
    import_docs.main()


def test_import_cli_missing_folder_exits_nonzero(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'argv',['import_docs','--path',str(tmp_path/'missing')])
    with pytest.raises(SystemExit) as exc:
        import_docs.main()
    assert exc.value.code == 1


@pytest.mark.parametrize('url',['https://example.com','http://user:pass@localhost:11434','http://localhost:11434/path'])
def test_settings_reject_nonlocal_or_nonorigin_urls(tmp_path,monkeypatch,url):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('OLLAMA_URL',url)
    with pytest.raises(ValueError,match='OLLAMA_URL'):
        Settings.load()


def test_settings_load_container_gateway_and_limits(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('OLLAMA_URL','http://host.containers.internal:11434')
    monkeypatch.setenv('DATABASE_BACKEND','sqlite')
    monkeypatch.setenv('MAX_UPLOAD_MB','150')
    settings = Settings.load()
    assert settings.max_upload_mb == 150
    assert settings.ollama_url.endswith(':11434')


def test_ollama_http_embedding_and_answer(tmp_path,monkeypatch):
    settings = Settings(tmp_path,'http://127.0.0.1:11434','chat','embed',.35)
    requests=[]
    def handler(request):
        requests.append(request)
        if request.url.path == '/api/embed':
            return httpx.Response(200,json={'embeddings':[[1.,0.]]})
        return httpx.Response(200,json={'message':{'content':'Evidence [1].'}})
    original = httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw: original(**kw,transport=httpx.MockTransport(handler)))
    model = Ollama(settings)
    assert model.embed(['query']) == [[1.,0.]]
    assert model.answer('question',[{'name':'note.md','page':1,'text':'evidence'}]) == 'Evidence [1].'
    assert requests[-1].url.path == '/api/chat'


def test_ollama_http_failure_is_sanitized(tmp_path,monkeypatch):
    settings = Settings(tmp_path,'http://127.0.0.1:11434','chat','embed',.35)
    original = httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw: original(**kw,transport=httpx.MockTransport(lambda r:httpx.Response(500))))
    with pytest.raises(RagError):
        Ollama(settings).request('/api/tags')


def test_postgres_backup_creates_binary_archive(tmp_path,monkeypatch):
    output = tmp_path/'backup.dump'
    monkeypatch.setattr(sys,'argv',['postgres_backup','backup','--file',str(output)])
    def run(argv,**kwargs):
        assert argv[-2:] == ['--data-only','--format=custom']
        assert kwargs['check']
        kwargs['stdout'].write(b'PGDMP archive')
    monkeypatch.setattr(postgres_backup.subprocess,'run',run)
    postgres_backup.main()
    assert output.read_bytes().startswith(b'PGDMP')


def test_failed_postgres_backup_removes_partial_file(tmp_path,monkeypatch):
    output = tmp_path/'failed.dump'
    monkeypatch.setattr(sys,'argv',['postgres_backup','backup','--file',str(output)])
    def fail(argv,**kwargs):
        kwargs['stdout'].write(b'partial')
        raise subprocess.CalledProcessError(1,argv)
    monkeypatch.setattr(postgres_backup.subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError):
        postgres_backup.main()
    assert not output.exists()


def test_postgres_restore_refuses_nonempty_target(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'argv',['postgres_backup','restore','--file','unused.dump'])
    monkeypatch.setattr(postgres_backup.Settings,'load',lambda: object())
    monkeypatch.setattr(postgres_backup,'PostgresStore',lambda settings:SimpleNamespace(documents=lambda:[{'id':'existing'}]))
    monkeypatch.setattr(postgres_backup.subprocess,'run',lambda *a,**kw:pytest.fail('Restore must not run'))
    with pytest.raises(SystemExit) as exc:
        postgres_backup.main()
    assert exc.value.code == 2
