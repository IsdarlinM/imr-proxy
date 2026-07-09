# Usage

Start with `imr-proxy start --web --terminal` and configure your browser to `127.0.0.1:7413`.

## References

- OWASP ASVS
- OWASP WSTG
- OWASP Secure Headers Project
- MDN HTTP headers
- mitmproxy documentation
- Python cryptography documentation


## First Web UI login

Open `http://127.0.0.1:7414/` and log in with the first-run credentials `admin:admin`. Change the password immediately:

```bash
imr-proxy users passwd admin --password "NewStrongPassword"
```
