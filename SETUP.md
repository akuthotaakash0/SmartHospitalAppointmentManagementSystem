Setup and Run (Google Sign-In + LAN access)

1) Create Google OAuth credentials
- Go to Google Cloud Console -> APIs & Services -> Credentials -> Create Credentials -> OAuth client ID.
- Application type: Web application.
- Authorized redirect URIs: add `http://<HOST>:5000/auth/callback` (replace `<HOST>` with `localhost` for local-only testing or your machine LAN IP for other devices).
- Copy `CLIENT_ID` and `CLIENT_SECRET`.

2) Configure environment variables
- Copy `.env.example` to `.env` or export vars in your shell.
- Example (PowerShell temporary for session):
```powershell
$env:GOOGLE_CLIENT_ID="YOUR_CLIENT_ID"
$env:GOOGLE_CLIENT_SECRET="YOUR_CLIENT_SECRET"
$env:SECRET_KEY="some-random-secret"
# Optional mail
$env:MAIL_USERNAME="your-email@gmail.com"
$env:MAIL_PASSWORD="your-email-password"
```

3) Install dependencies
```bash
pip install -r requirements.txt
```

4) Run the app
```bash
python app.py
```
- The app listens on port 5000 and binds to all interfaces (`0.0.0.0`).

5) Access from another device on the same LAN
- Find your host IPv4 address (PowerShell):
```powershell
ipconfig
```
- Open in the other device's browser: `http://<HOST_IPV4>:5000`

6) Windows firewall (allow inbound TCP 5000)
- Elevated PowerShell:
```powershell
New-NetFirewallRule -DisplayName "Flask 5000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000
```

7) If you need public access (internet)
- Use a tunneling service like ngrok:
```bash
ngrok http 5000
```
- Share the ngrok URL. Note: keep security in mind.

Optional: use `client_secret.json`
- Instead of setting `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` env vars, you can place your downloaded credentials file into the project root as `client_secret.json` or `client_secret.json.example`.
- The app will attempt to read `client_id` and `client_secret` from that file automatically.

Example format (already provided as `client_secret.json.example`):
```json
{
	"web": {
		"client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
		"client_secret": "YOUR_CLIENT_SECRET",
		"redirect_uris": ["http://localhost:5000/auth/callback"]
	}
}
```
Notes
- Make sure the redirect URI you register in Google matches the URL used by clients exactly (host and port).
- For production, use HTTPS and proper secret management.
