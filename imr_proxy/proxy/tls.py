def extract_tls_metadata(flow)->dict[str,str]:
    meta={}
    sc=getattr(flow, "server_conn", None)
    for attr in ("cert","tls_version","cipher"):
        val=getattr(sc, attr, None)
        if val: meta[attr]=str(val)
    return meta
