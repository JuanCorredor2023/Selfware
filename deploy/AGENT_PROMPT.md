# Prompt for the agent that runs on the VM

Paste everything below the line into the agent that has a shell on the VM.

---

You are deploying the Atlas (Selfware) app on this VM. Repo: <REPO_URL>, branch `main-vm`.
Everything you need is in the repo's `deploy/` folder: read `deploy/README.md` first and follow it.

What I will tell you in this conversation: the public address (IP or domain), and any
changes I want to the nginx or systemd setup. Ask me for anything else you are missing.

Rules:
- Do the steps in `deploy/README.md` in order. Do not change application code. If something in
  `deploy/` does not fit this VM, change the file under `deploy/`, tell me what and why.
- Secrets: ask me for `NEBIUS_API_KEY` and write it only into `/etc/selfware/selfware.env`
  (mode 600). Never print it, log it, or commit it.
- Start with `SELFWARE_AGENT=mock` unless I say the index folder is already on the VM. Real
  mode spends credits: do not send real questions to `/ask` without asking me first.
- Do not open firewall ports, install certificates or touch other nginx sites unless I say so.
  Tell me which ports must be open (80, and 443 if we add HTTPS).
- Keep one uvicorn worker (the cost ledger is in memory).
- After each step, verify it: `nginx -t`, `systemctl status selfware-api`, then
  `curl http://127.0.0.1:8000/health` and `curl http://<address>/health`.

Done means: the dashboard loads at `http://<address>/`, `/health` is ok, one mock `/ask` returns an
answer, and `/cost` reflects it. Then report: what you installed, the files you created or
edited (with paths), the commands to restart or update (`deploy/deploy.sh`), and anything
still pending.
