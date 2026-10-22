import json
import httpx
import pytest
from esg_backend.storage import StorageError, SupabaseStorage


def storage(handler):
    return SupabaseStorage('https://project.supabase.co', 'secret-server-key', 'esg-evidence', httpx.Client(transport=httpx.MockTransport(handler)))


def test_upload_is_immutable_and_encodes_path():
    def handler(request):
        assert request.method == 'POST'
        assert request.url.raw_path == b'/storage/v1/object/esg-evidence/company/a%20b.pdf'
        assert request.headers['x-upsert'] == 'false'
        assert request.headers['content-type'] == 'application/pdf'
        assert request.headers['apikey'] == 'secret-server-key'
        assert request.content == b'evidence'
        return httpx.Response(200)
    storage(handler).upload('company/a b.pdf', b'evidence', 'application/pdf')


def test_download_and_delete_use_private_object_api():
    def handler(request):
        if request.method == 'GET':
            assert request.url.path == '/storage/v1/object/esg-evidence/company/file.pdf'
            return httpx.Response(200, content=b'evidence')
        assert request.method == 'DELETE'
        assert json.loads(request.content) == {'prefixes': ['company/file.pdf']}
        return httpx.Response(200, json=[])
    backend = storage(handler)
    assert backend.download('company/file.pdf') == b'evidence'
    backend.delete(['company/file.pdf'])


def test_create_missing_private_bucket_with_size_limit():
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'GET':
            return httpx.Response(404)
        assert json.loads(request.content) == {'id': 'esg-evidence', 'name': 'esg-evidence', 'public': False, 'file_size_limit': 10485760}
        return httpx.Response(200)
    storage(handler).ensure_bucket()
    assert calls == ['GET', 'POST']


def test_existing_public_bucket_is_refused_without_mutation():
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={'public': True})
    with pytest.raises(StorageError, match='private'):
        storage(handler).ensure_bucket()
    assert calls == ['GET']


def test_existing_private_bucket_is_verified():
    storage(lambda r: httpx.Response(200, json={'public': False, 'file_size_limit': 10485760})).ensure_bucket()


def test_errors_never_include_server_response_or_credentials():
    with pytest.raises(StorageError) as error:
        storage(lambda r: httpx.Response(401, text='secret-server-key confidential content')).download('company/file.pdf')
    assert 'secret' not in str(error.value)
    assert 'confidential' not in str(error.value)
    assert '401' in str(error.value)


def test_transport_errors_are_sanitized():
    def handler(request):
        raise httpx.ConnectError('secret-server-key confidential content')
    with pytest.raises(StorageError, match='unavailable') as error:
        storage(handler).download('company/file.pdf')
    assert 'secret' not in str(error.value)


def test_oversized_upload_is_rejected_before_network():
    with pytest.raises(StorageError, match='10 MB'):
        storage(lambda r: pytest.fail('oversized upload reached network')).upload('a.pdf', b'x' * (10485760 + 1), 'application/pdf')


@pytest.mark.parametrize('path', ['', '../secret', 'company/../secret', '/absolute', 'a//b'])
def test_invalid_object_paths_are_rejected(path):
    with pytest.raises(StorageError, match='path'):
        storage(lambda r: pytest.fail('invalid path reached network')).download(path)


def test_supabase_missing_bucket_error_is_created():
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'GET':
            return httpx.Response(400, json={'statusCode': '404', 'error': 'not_found', 'message': 'Bucket not found'})
        return httpx.Response(200)
    storage(handler).ensure_bucket()
    assert calls == ['GET', 'POST']


def test_private_bucket_limit_is_restricted_without_changing_visibility():
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'public': False, 'file_size_limit': None})
        assert request.method == 'PUT'
        assert json.loads(request.content) == {'public': False, 'file_size_limit': 10485760}
        return httpx.Response(200)
    storage(handler).ensure_bucket()


def test_malformed_bucket_limit_is_sanitized():
    with pytest.raises(StorageError, match='verify'):
        storage(lambda r: httpx.Response(200, json={'public': False, 'file_size_limit': 'secret'})).ensure_bucket()
