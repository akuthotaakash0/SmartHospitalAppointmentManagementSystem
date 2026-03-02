# Hospital CSV Project – Google OAuth Setup

This project uses Flask and a simple CSV-backed user store. I added Google OAuth (Authlib) support.

Quick setup (Windows / PowerShell):

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Create a Google OAuth 2.0 Client ID:
   - Go to Google Cloud Console → APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Web application
   - Authorized redirect URI: `http://localhost:5000/google_callback`
   - Copy the Client ID and Client secret

3. Create a `.env` file in the project root (you can copy `.env.example`):

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
SECRET_KEY=some-secret
```

4. Run the app:

```powershell
python app.py
```
 
 Dev helper — auto-open Google OAuth for testing
 
 Set `OPEN_GOOGLE_TEST=1` (or add it to your `.env`) to automatically open the OAuth flow in your browser when the server starts:
 
 ```powershell
# temporary for session
$env:OPEN_GOOGLE_TEST=1
python app.py
```

Notes:
- The app will load environment variables from `.env` automatically.
- If you prefer environment variables globally, use `setx` or set them in your host environment.
- OAuth users are created in `users.csv` with an empty password field.

If you want, I can also add stricter checks (e.g., require verified email or restrict registration by domain).