"""Bound ingest bytes before JSON/Pydantic parsing, including chunked bodies."""
import json
from evidence import strict_json


class IngestBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path')
        if scope['type'] != 'http' or scope.get('method') != 'POST' or path not in ('/api/events','/api/events/batch'):
            return await self.app(scope,receive,send)
        limit = 32768 if path == '/api/events' else 2097152
        headers = dict(scope.get('headers',[]))

        async def reject(status, detail):
            body = json.dumps({'detail':detail}).encode()
            await send({'type':'http.response.start','status':status,'headers':[
                (b'content-type',b'application/json'),(b'content-length',str(len(body)).encode()),
                (b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),
                (b'x-frame-options',b'DENY'),(b'referrer-policy',b'no-referrer')]})
            await send({'type':'http.response.body','body':body})

        if headers.get(b'content-type',b'').split(b';')[0].strip().lower() != b'application/json':
            return await reject(415,'Ingestion requires application/json')
        try:
            length = int(headers.get(b'content-length',b'0'))
            if length < 0:
                raise ValueError()
        except ValueError:
            return await reject(400,'Invalid content length')
        if length > limit:
            return await reject(413,'Ingestion body too large')
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body',b'')
            size += len(chunk)
            if size > limit:
                return await reject(413,'Ingestion body too large')
            chunks.append(chunk)
            if not message.get('more_body',False):
                break
        body = b''.join(chunks)
        try:
            strict_json(body)  # Reject duplicate keys/non-finite numbers, with no input echo.
        except (ValueError,UnicodeError,RecursionError):
            return await reject(422,'Invalid JSON body')
        consumed = False
        async def bounded_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        await self.app(scope,bounded_receive,send)
