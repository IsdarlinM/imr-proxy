import string
def is_probably_binary(data: bytes)->bool:
    if not data: return False
    if b"\x00" in data: return True
    sample=data[:1024]; printable=set(bytes(string.printable,"ascii"))
    return sum(1 for b in sample if b not in printable)/max(len(sample),1)>0.30
def decode_body(data: bytes, max_size: int, capture: bool=True)->tuple[str|None,int,bool]:
    size=len(data or b"")
    if not capture or size==0: return None,size,False
    if size>max_size: return f"[body omitted: {size} bytes exceeds max_body_size={max_size}]",size,False
    if is_probably_binary(data): return "[binary body omitted]",size,True
    return data.decode("utf-8", errors="replace"),size,False
def headers_to_dict(headers)->dict[str,str]:
    try: return {str(k):str(v) for k,v in headers.items(multi=False)}
    except Exception:
        try: return {str(k):str(v) for k,v in headers.items()}
        except Exception: return {}
