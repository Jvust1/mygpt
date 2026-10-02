"""Desktop-only extension; legacy Book/Brain authorization remains unchanged."""
from http.cookies import SimpleCookie
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit
from desktop_chat import DesktopChat
from mygpt_brain.local_service import LocalBrainHandler, LocalServiceError
from desktop_state import Store, MAX_BYTES

COOKIE = 'mygpt_workspace'
CLIENT = 'mygpt-desktop-v1'


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
        if urlsplit(self.path).path == '/desktop-api/chat-history':
            try:
                self._workspace_guard()
                query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, strict_parsing=True)
                if set(query) - {'before'} or any(len(v) != 1 for v in query.values()):
                    raise ValueError('invalid_history_cursor')
                before = int(query['before'][0]) if 'before' in query else None
                return self._json(200, self.server.desktop_chat.history(before))
            except LocalServiceError as error: return self._error(error)
            except ValueError: return self._error(LocalServiceError('invalid_history_request', 400))
            except Exception: return self._error(LocalServiceError('chat_history_read_failed', 500))
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
                result = self.server.desktop_chat.send(value)
            else: raise LocalServiceError('not_found',404)
            return self._json(200,result)
        except LocalServiceError as error: return self._error(error)
        except ValueError as error: return self._error(LocalServiceError(str(error),429 if str(error)=='model_busy' else 409 if str(error) in ('revision_conflict','request_id_conflict','chat_outcome_unknown_check_history_no_automatic_retry') else 400))
        except Exception: return self._error(LocalServiceError('workspace_operation_failed_preserve_draft',500))


def extend(server, home):
    server.httpd.workspace = Store(Path(home)/'data')
    server.httpd.workspace_token = secrets.token_urlsafe(32)
    server.httpd.desktop_chat = DesktopChat(Path(home)/'data')
    server.httpd.RequestHandlerClass = WorkspaceHandler
    return server
