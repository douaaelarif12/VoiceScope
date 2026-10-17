"""Bound the request before multipart parsing, including chunked uploads."""
from starlette.responses import PlainTextResponse

class BodyLimitMiddleware:
    def __init__(self,app,max_bytes):
        self.app,self.max_bytes=app,max_bytes

    async def __call__(self,scope,receive,send):
        if scope["type"]!="http" or scope["method"] not in ("POST","PUT","PATCH"):
            return await self.app(scope,receive,send)
        chunks,size=[],0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect":
                return
            body=message.get("body",b"")
            size+=len(body)
            if size>self.max_bytes:
                return await PlainTextResponse("Téléversement trop volumineux",status_code=413)(scope,receive,send)
            chunks.append(body)
            if not message.get("more_body",False):
                break
        body=b"".join(chunks)
        chunks.clear()
        delivered=False
        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered=True
            return {"type":"http.request","body":body,"more_body":False}
        return await self.app(scope,replay,send)
