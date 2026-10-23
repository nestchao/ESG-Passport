"""Private, server-only Supabase Storage adapter."""
from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx

MAX_FILE_BYTES = 10 * 1024 * 1024


class StorageError(RuntimeError):
    """A sanitized evidence storage failure safe to present to API callers."""


class Storage(Protocol):
    def upload(self, path: str, content: bytes, content_type: str) -> None: ...
    def download(self, path: str) -> bytes: ...
    def delete(self, paths: list[str]) -> None: ...
    def ensure_bucket(self) -> None: ...


class SupabaseStorage:
    def __init__(self, url: str, key: str, bucket: str, client: httpx.Client | None = None):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            raise StorageError('Configure SUPABASE_URL as an HTTPS project URL.')
        if not key or not bucket or '/' in bucket:
            raise StorageError('Configure a server key and a valid private storage bucket.')
        self.base_url = url.rstrip('/') + '/storage/v1'
        self.bucket = bucket
        self.client = client or httpx.Client(timeout=30.0, follow_redirects=False)
        self.headers = {'apikey': key}
        # Modern secret keys are opaque API keys, not JWTs. Legacy service-role
        # JWTs also need their bearer header on private Storage requests.
        if not key.startswith('sb_secret_'):
            self.headers['Authorization'] = f'Bearer {key}'

    def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        headers = dict(self.headers)
        headers.update(kwargs.pop('headers', {}))
        try:
            response = self.client.request(method, self.base_url + endpoint, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise StorageError('Evidence storage is unavailable. Please retry.') from None
        return response

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if not response.is_success:
            raise StorageError(f'Evidence storage request failed (HTTP {response.status_code}).')

    @staticmethod
    def _path(path: str) -> str:
        if not isinstance(path, str) or not path or '\\' in path or any(c in path for c in '\r\n\0'):
            raise StorageError('Invalid evidence object path.')
        if any(part in ('', '.', '..') for part in path.split('/')):
            raise StorageError('Invalid evidence object path.')
        return quote(path, safe='/')

    def _object_url(self, path: str) -> str:
        return '/object/' + quote(self.bucket, safe='') + '/' + self._path(path)

    def upload(self, path: str, content: bytes, content_type: str) -> None:
        endpoint = self._object_url(path)
        if len(content) > MAX_FILE_BYTES:
            raise StorageError('Evidence files must be 10 MB or smaller.')
        response = self._request('POST', endpoint, content=content, headers={
            'Content-Type': content_type, 'x-upsert': 'false',
        })
        self._check(response)

    def download(self, path: str) -> bytes:
        response = self._request('GET', self._object_url(path))
        self._check(response)
        return response.content

    def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        for path in paths:
            self._path(path)
        response = self._request('DELETE', '/object/' + quote(self.bucket, safe=''), json={'prefixes': paths})
        self._check(response)

    def ensure_bucket(self) -> None:
        endpoint = '/bucket/' + quote(self.bucket, safe='')
        response = self._request('GET', endpoint)
        missing = response.status_code == 404
        if response.status_code == 400:
            try:
                error = response.json()
                missing = isinstance(error, dict) and str(error.get('statusCode')) == '404'
            except ValueError:
                pass
        if missing:
            created = self._request('POST', '/bucket', json={
                'id': self.bucket, 'name': self.bucket, 'public': False,
                'file_size_limit': MAX_FILE_BYTES,
            })
            if created.status_code not in (400, 409):
                self._check(created)
                return
            # Concurrent creation or an existing-name conflict: verify privacy.
            response = self._request('GET', endpoint)
        self._check(response)
        try:
            metadata = response.json()
        except ValueError:
            raise StorageError('Unable to verify the private evidence bucket.') from None
        if not isinstance(metadata, dict) or metadata.get('public') is not False:
            raise StorageError('The evidence bucket must be private; review its Supabase configuration.')
        limit = metadata.get('file_size_limit')
        try:
            oversized_limit = limit is None or int(limit) > MAX_FILE_BYTES
        except (TypeError, ValueError):
            raise StorageError('Unable to verify the private evidence bucket size limit.') from None
        if oversized_limit:
            updated = self._request('PUT', endpoint, json={'public': False, 'file_size_limit': MAX_FILE_BYTES})
            self._check(updated)
