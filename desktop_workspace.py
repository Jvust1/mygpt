"""Desktop-only extension; legacy Book/Brain authorization remains unchanged."""
from http.cookies import SimpleCookie
import json
from pathlib import Path
import secrets
import threading
from urllib.error import URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from mygpt_brain.local_service import LocalBrainHandler, LocalServiceError
from desktop_state import Store, MAX_BYTES

COOKIE = 'mygpt_workspace'
CLIENT = 'mygpt-desktop-v1'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('local_model_redirect_refused')


def local_chat(value):
    if not isinstance(value, dict) or set(value) != {'consent', 'port', 'model', 'prompt'} or value['consent'] is not True:
        raise ValueError('explicit_consent_required')
    port, model, prompt = value['port'], value['model'], value['prompt']
    if type(port) is not int or not 1 <= port <= 65535: raise ValueError('invalid_local_port')
    if not isinstance(model, str) or not model.strip() or len(model) > 160 or 'cloud' in model.lower():
        raise ValueError('local_model_name_required')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000: raise ValueError('invalid_prompt')
    body = json.dumps({'model': model, 'stream': False, 'keep_alive': '0',
        'messages': [{'role': 'system', 'content': '你是mygpt学习助手。诚实区分来源与推断；不声称看到了屏幕或Book实时状态。不把学习时长当作掌握证明。'},
                     {'role': 'user', 'content': prompt}], 'options': {'num_predict': 2048}}).encode()
    request = Request(f'http://127.0.0.1:{port}/api/chat', data=body,
                      headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=90) as response:
            raw = response.read(MAX_BYTES+1)
    except (URLError, OSError):
        raise ValueError('local_model_unavailable_no_automatic_retry') from None
    if len(raw) > MAX_BYTES: raise ValueError('model_response_too_large')
    try:
        data = json.loads(raw); reply = data['message']['content']
        if not isinstance(reply, str) or not reply.strip(): raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError('invalid_model_response') from None
    return {'reply': reply, 'origin': 'USER_CONFIGURED_LOCAL_OLLAMA', 'quality_verified': False}


class WorkspaceHandler(LocalBrainHandler):
    def _workspace_guard(self, post=False):
        for name in ('Host','Origin','Cookie','Sec-Fetch-Site','Content-Length','Content-Type','Transfer-Encoding','X-MyGPT-Client'):
            if len(self.headers.get_all(name, [])) > 1: raise LocalServiceError('duplicate_header', 400)
        if self.client_address[0] != '127.0.0.1' or self.headers.get('Host') != self.server.expected_host:
            raise LocalServiceError('invalid_host', 403)
        if self.headers.get('X-MyGPT-Client') != CLIENT: raise LocalServiceError('invalid_client', 403)
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            valid = cookie.get(COOKIE) and secrets.compare_digest(cookie[COOKIE].value, self.server.workspace_token)
        except Exception: valid = False
        if not valid: raise LocalServiceError('unauthorized', 403)
        site, origin = self.headers.get('Sec-Fetch-Site'), self.headers.get('Origin')
        if site not in (None, 'same-origin') or origin not in (None, self.server.origin):
            raise LocalServiceError('cross_site_request', 403)
        if origin is None and site != 'same-origin': raise LocalServiceError('origin_required', 403)
        if post and (origin != self.server.origin or self.headers.get('Transfer-Encoding')):
            raise LocalServiceError('invalid_post_origin_or_transfer', 403)
        if post and self.headers.get_content_type() != 'application/json': raise LocalServiceError('json_required', 415)

    def _headers(self, status, content_type, length, *, cookie=False):
        if self.path in ('/desktop/', '/desktop/index.html') and status == 200:
            self.send_response(status)
            for key, value in {'Content-Type':content_type, 'Content-Length':str(length), 'Connection':'close',
                'Cache-Control':'no-store', 'X-Frame-Options':'DENY', 'X-Content-Type-Options':'nosniff',
                'Referrer-Policy':'no-referrer', 'Cross-Origin-Resource-Policy':'same-origin',
                'Set-Cookie':f'{COOKIE}={self.server.workspace_token}; HttpOnly; SameSite=Strict; Path=/desktop-api/'}.items():
                self.send_header(key,value)
            self.close_connection=True; self.end_headers()
        else: super()._headers(status,content_type,length,cookie=cookie)

    def do_GET(self):
        if self.path in ('/desktop/', '/desktop/index.html', '/desktop/app.js'):
            if self.client_address[0] != '127.0.0.1' or self.headers.get_all('Host',[]) != [self.server.expected_host]:
                return self._error(LocalServiceError('invalid_host',403))
            name = 'app.js' if self.path.endswith('.js') else 'index.html'
            try: raw = (self.server.root/'desktop_ui'/name).read_bytes()
            except OSError: return self._error(LocalServiceError('not_found',404))
            return self._send(200,raw,'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/html; charset=utf-8')
        if self.path == '/desktop-api/state':
            try:
                self._workspace_guard(); return self._json(200,self.server.workspace.read())
            except LocalServiceError as error: return self._error(error)
            except (ValueError, OSError): return self._error(LocalServiceError('workspace_read_failed',500))
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith('/desktop-api/'): return super().do_POST()
        try:
            self._workspace_guard(post=True)
            value = self._read_json(MAX_BYTES+4096)
            if self.path == '/desktop-api/state':
                if set(value) != {'revision','value'}: raise ValueError('invalid_request')
                result = self.server.workspace.save(value['revision'],value['value'])
            elif self.path == '/desktop-api/merge': result = self.server.workspace.merge(value)
            elif self.path == '/desktop-api/local-chat':
                if not self.server.chat_slot.acquire(blocking=False): raise LocalServiceError('model_busy',429)
                try: result = local_chat(value)
                finally: self.server.chat_slot.release()
            else: raise LocalServiceError('not_found',404)
            return self._json(200,result)
        except LocalServiceError as error: return self._error(error)
        except ValueError as error: return self._error(LocalServiceError(str(error),409 if str(error)=='revision_conflict' else 400))
        except Exception: return self._error(LocalServiceError('workspace_operation_failed_preserve_draft',500))


def extend(server, home):
    server.httpd.workspace = Store(Path(home)/'data')
    server.httpd.workspace_token = secrets.token_urlsafe(32)
    server.httpd.chat_slot = threading.BoundedSemaphore(1)
    server.httpd.RequestHandlerClass = WorkspaceHandler
    return server
