# Deploying Atlas to a VM

One VM, one API process, nginx in front, the dashboard as static files.

```
browser -> nginx :80 --+-- /  (web/dist, static)
                       +-- /ask /cost /para /projects /areas /resources /archive /health -> uvicorn 127.0.0.1:8000
```

Same origin for both, so the API needs no CORS change. Run **one** uvicorn worker: the
cost ledger behind `/cost` is in memory.

## One-time setup

1. Packages: `git`, `nginx`, `curl`, Node 20+, and [uv](https://docs.astral.sh/uv/) at `/usr/local/bin/uv`
   (uv installs Python 3.14 by itself on first `uv sync`).
2. A `selfware` user and folders:
   ```bash
   sudo useradd --system --create-home --shell /bin/bash selfware
   sudo mkdir -p /srv/selfware/data /etc/selfware && sudo chown -R selfware: /srv/selfware
   ```
3. Code, as `selfware`: `git clone -b main-vm <repo-url> /srv/selfware/app`
4. Secrets and settings: copy `deploy/selfware.env.example` to `/etc/selfware/selfware.env`,
   `chmod 600`, set `NEBIUS_API_KEY`. Never commit this file.
5. Data: put an index folder at the `SELFWARE_CHROMA_PATH` (for the evaluation corpus, the
   Enron index built by `scripts/index_enron.py`; it is not in the repo).
   With no index yet, set `SELFWARE_AGENT=mock` in the env file: the app runs on simulated data.
6. Services:
   ```bash
   sudo cp deploy/selfware-api.service /etc/systemd/system/ && sudo systemctl daemon-reload
   sudo systemctl enable selfware-api
   sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/selfware   # set server_name
   sudo ln -s /etc/nginx/sites-available/selfware /etc/nginx/sites-enabled/selfware
   sudo nginx -t && sudo systemctl reload nginx
   ```
7. First build and start (as `selfware`): `PUBLIC_URL=http://<ip-or-domain> ./deploy/deploy.sh`

`selfware` needs passwordless sudo only for `systemctl restart selfware-api`.

## Update

`PUBLIC_URL=http://<ip-or-domain> ./deploy/deploy.sh` (pull, `uv sync --locked`, dashboard build, restart).

## Check it works

```bash
curl -s http://<host>/health          # {"status":"ok"}
curl -s "http://<host>/ask?q=test&strategy=flat"
curl -s http://<host>/cost            # query_count goes up after each /ask
journalctl -u selfware-api -f         # OpenTelemetry spans (token_factory.call) print here
```

In real mode, `/ask` spends credits: one Ultra call, plus a Super call with `strategy=para`.

## HTTPS

Not set up here. With a domain, use certbot for nginx, then set `PUBLIC_URL=https://...`
and redeploy so the dashboard is built against the https origin.
