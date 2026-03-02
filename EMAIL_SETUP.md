# Email Notifications Setup

Your hospital application now sends email notifications for:
- ✅ User registration (welcome email)
- ✅ Appointment confirmation (booking confirmation)
- ✅ Appointment cancellation (admin cancels appointment)

## Setup Instructions

### 1. Install Flask-Mail
```powershell
pip install -r requirements.txt
```

### 2. Configure Email in .env File

Create a `.env` file in the project root with the following variables:

```env
# Email Configuration (Gmail example)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@hospital.com
```

### 3. Get Gmail App Password

If using **Gmail**:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable "2-Step Verification" (if not already enabled)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select "Mail" and "Windows Computer"
5. Generate an App Password
6. Copy the 16-character password to your `.env` file as `MAIL_PASSWORD`

⚠️ **Do NOT use your regular Gmail password** - use the App Password instead!

### 4. Alternative Email Providers

**For Outlook/Office365:**
```env
MAIL_SERVER=smtp-mail.outlook.com
MAIL_PORT=587
MAIL_USERNAME=your-email@outlook.com
MAIL_PASSWORD=your-password
```

**For SendGrid:**
```env
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
```

## Testing Email Functionality

1. Register a new user account
2. Check your email (or spam folder) for welcome email
3. Book an appointment and confirm it
4. Check your email for confirmation
5. (Admin) Delete an appointment from admin dashboard
6. Check your email for cancellation notice

## Troubleshooting

**Emails not sending?**
- Verify `MAIL_USERNAME` and `MAIL_PASSWORD` are correct
- Check the console for error messages
- For Gmail, ensure App Password (not regular password) is used
- Check firewall/network settings for port 587 access

**Email configuration not recognized?**
- Ensure `.env` file is in the project root directory
- Restart the Flask application after updating `.env`
- Check that environment variables are loaded correctly

**Still having issues?**
- The app will continue to work without email
- Check console logs for detailed error messages
- Falls back to in-app notifications if email fails

## Email Configuration Details

The email system uses Flask-Mail with the following configuration:

```python
app.config['MAIL_SERVER'] = smtp server address
app.config['MAIL_PORT'] = 587 (TLS port)
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = your email
app.config['MAIL_PASSWORD'] = mldj wvan dzwf rxdw
```

Email is sent asynchronously in the background - registration and confirmations happen instantly without delays.
