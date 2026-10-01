"""Real loopback asset delivery; no browser, model, private source or external IO."""
from hashlib import sha256
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from mygpt_brain.local_service import create_local_server


def test_real_loopback_serves_exact_renderer_and_only_explicit_public_assets():
    with create_local_server(enable_selection_intake=True) as server:
        with urlopen(server.origin + '/third_party/katex/katex.mjs', timeout=3) as response:
            assert response.status == 200
            assert response.headers['Content-Type'].startswith(('text/javascript', 'application/javascript'))
            assert response.headers['X-Content-Type-Options'] == 'nosniff'
            assert sha256(response.read()).hexdigest() == '694a531495903e374957e9a9c904a402e2f413762635df486c4cf6163320d1aa'
        with urlopen(server.origin + '/host/math-preview.js', timeout=3) as response:
            assert b"output:'mathml'" in response.read()
        for path in ['/third_party/katex/LICENSE', '/third_party/katex/fonts/KaTeX_Main-Regular.woff2', '/third_party/katex/../katex/LICENSE']:
            with pytest.raises(HTTPError) as caught:
                urlopen(server.origin + path, timeout=3)
            assert caught.value.code == 404
        assert server.httpd.engine.status()['requests_started'] == 0
