import httpx
from imr_proxy.models.flow import FlowRecord
SAFE_REPLAY_METHODS={"GET","HEAD","OPTIONS"}
def replay_flow(flow: FlowRecord, allow_unsafe: bool=False, timeout: float=15.0)->httpx.Response:
    method=flow.request.method.upper()
    if method not in SAFE_REPLAY_METHODS and not allow_unsafe:
        raise ValueError(f"Refusing to replay unsafe method {method}.")
    headers={k:v for k,v in flow.request.headers.items() if k.lower() not in {"host","content-length"}}
    body=flow.request.body_text.encode() if allow_unsafe and flow.request.body_text else None
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        return client.request(method, flow.request.url, headers=headers, content=body)
