import os, shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
@dataclass(frozen=True)
class CAPaths:
    ca_dir: Path; key: Path; cert: Path; mitmproxy_combined: Path; mitmproxy_cert: Path
def ca_paths(ca_dir: Path)->CAPaths:
    d=ca_dir.expanduser().resolve()
    return CAPaths(d, d/"imr-proxy-ca.key.pem", d/"imr-proxy-ca.cert.pem", d/"mitmproxy-ca.pem", d/"mitmproxy-ca-cert.pem")
def _chmod(path: Path, mode: int):
    try: os.chmod(path, mode)
    except OSError: pass
def init_ca(ca_dir: Path, common_name: str="imr-proxy Local Testing CA", force: bool=False)->CAPaths:
    p=ca_paths(ca_dir); p.ca_dir.mkdir(parents=True, exist_ok=True)
    if p.key.exists() and not force: raise FileExistsError(f"CA already exists: {p.ca_dir}")
    key=rsa.generate_private_key(public_exponent=65537, key_size=4096)
    subject=issuer=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,common_name), x509.NameAttribute(NameOID.ORGANIZATION_NAME,"imr-proxy authorized local testing")])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365*3)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_cert_sign=True,crl_sign=True,key_encipherment=False,content_commitment=False,data_encipherment=False,key_agreement=False,encipher_only=False,decipher_only=False),critical=True).sign(key,hashes.SHA256()))
    kb=key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
    cb=cert.public_bytes(serialization.Encoding.PEM)
    p.key.write_bytes(kb); _chmod(p.key,0o600)
    p.cert.write_bytes(cb); _chmod(p.cert,0o644)
    p.mitmproxy_combined.write_bytes(kb+cb); _chmod(p.mitmproxy_combined,0o600)
    p.mitmproxy_cert.write_bytes(cb); _chmod(p.mitmproxy_cert,0o644)
    return p
def export_ca(ca_dir: Path, output: Path, fmt: str="pem")->Path:
    p=ca_paths(ca_dir)
    if not p.cert.exists(): raise FileNotFoundError(f"CA certificate not found: {p.cert}")
    if fmt.lower() not in {"pem","crt","cer"}: raise ValueError("Only public PEM/CRT/CER export is supported")
    out=output.expanduser().resolve(); out.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p.cert,out); _chmod(out,0o644); return out
def rotate_ca(ca_dir: Path)->CAPaths:
    p=ca_paths(ca_dir)
    if p.ca_dir.exists(): shutil.move(str(p.ca_dir), str(p.ca_dir.with_name(p.ca_dir.name+".rotated-"+datetime.now().strftime("%Y%m%d%H%M%S"))))
    return init_ca(ca_dir, force=True)
def load_ca_info(ca_dir: Path)->dict[str,str]:
    p=ca_paths(ca_dir)
    if not p.cert.exists(): raise FileNotFoundError(f"CA certificate not found: {p.cert}")
    cert=x509.load_pem_x509_certificate(p.cert.read_bytes())
    return {"ca_dir":str(p.ca_dir),"subject":cert.subject.rfc4514_string(),"serial":str(cert.serial_number),"not_valid_before":cert.not_valid_before_utc.isoformat(),"not_valid_after":cert.not_valid_after_utc.isoformat(),"cert":str(p.cert),"key":str(p.key),"mitmproxy_combined":str(p.mitmproxy_combined)}
def sign_host_certificate(ca_dir: Path, hostname: str, output_dir: Path|None=None)->tuple[Path,Path]:
    p=ca_paths(ca_dir)
    ca_key=serialization.load_pem_private_key(p.key.read_bytes(), password=None)
    ca_cert=x509.load_pem_x509_certificate(p.cert.read_bytes())
    key=rsa.generate_private_key(public_exponent=65537, key_size=2048); now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,hostname)])).issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=90)).add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(ca_key,hashes.SHA256()))
    out=(output_dir or p.ca_dir/"leaf").expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    cert_path=out/f"{hostname}.cert.pem"; key_path=out/f"{hostname}.key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    _chmod(cert_path,0o644); _chmod(key_path,0o600); return cert_path,key_path
