import httpx

from esg_backend.storage import SupabaseStorage


def test_modern_server_key_is_sent_only_as_api_key():
    requests = []
    def receive(request):
        requests.append(request)
        return httpx.Response(200, content=b'file')
    with httpx.Client(transport=httpx.MockTransport(receive)) as client:
        storage = SupabaseStorage('https://example.supabase.co', 'sb_secret_example', 'esg-evidence', client=client)
        storage.download('lim-carton/source.png')
    assert requests[0].headers['apikey'] == 'sb_secret_example'
    assert 'authorization' not in requests[0].headers


def test_legacy_server_jwt_retains_bearer_header():
    requests = []
    def receive(request):
        requests.append(request)
        return httpx.Response(200, content=b'file')
    with httpx.Client(transport=httpx.MockTransport(receive)) as client:
        storage = SupabaseStorage('https://example.supabase.co', 'eyJ.legacy.signature', 'esg-evidence', client=client)
        storage.download('lim-carton/source.png')
    assert requests[0].headers['Authorization'] == 'Bearer eyJ.legacy.signature'
