# Billipocket Authentication Manual Verification Guide

## Quick Verification Steps

Follow these steps to manually verify the authentication integration is working:

### 1. Start the Application
```bash
python run.py
```

### 2. Test Route Protection (Unauthenticated)

Open your browser and visit these URLs - they should all redirect to login:
- http://127.0.0.1:5010/
- http://127.0.0.1:5010/invoices
- http://127.0.0.1:5010/clients
- http://127.0.0.1:5010/settings

**Expected:** All redirect to `/auth/login?next=...`

### 3. Access Authentication Pages

These should be accessible without login:
- http://127.0.0.1:5010/auth/login ✅ (Login form)
- http://127.0.0.1:5010/auth/register ✅ (Registration form)

### 4. Create Admin User (if needed)
```bash
FLASK_APP=run.py flask create-admin admin admin@yourcompany.com --password SecurePassword123
```

### 5. Test Login Flow

1. Go to http://127.0.0.1:5010/auth/login
2. Log in with your admin credentials
3. Should redirect to dashboard with Estonian text
4. Check sidebar shows your username and "Admin" badge

### 6. Test Protected Functionality

After logging in, verify these work:
- **Dashboard:** Metrics, charts, recent invoices
- **Invoices:** List, create new, edit existing
- **Clients:** List, create new, edit existing
- **Settings:** Company settings, VAT rates, etc.

### 7. Test Navigation

Click through all sidebar links:
- Ülevaade (Dashboard)
- Arved (Invoices)
- Kliendid (Clients)
- Aruanded (Reports)
- Seaded (Settings)
- Profiil (Profile)
- Kasutajad (Users - admin only)

### 8. Test Admin Features

If logged in as admin:
- Go to "Kasutajad" (Users)
- Should see user list
- Test toggling admin status
- Test user deactivation

### 9. Test Logout

Click "Logi välja" (Logout) in sidebar
- Should redirect to login page
- Should show logout success message
- Verify you can't access protected routes again

### 10. Test User Management CLI

```bash
# List all users
FLASK_APP=run.py flask list-users

# Create regular user
FLASK_APP=run.py flask create-user testuser test@example.com --password TestPass123

# Make user admin
FLASK_APP=run.py flask make-admin testuser

# Deactivate user
FLASK_APP=run.py flask deactivate-user testuser
```

## Expected Behavior Summary

### ✅ What Should Work
- All routes protected with authentication
- Estonian language throughout
- Existing invoice/client functionality unchanged
- Admin can manage users
- CSRF protection on forms
- Secure password handling
- Session persistence

### ❌ What Should NOT Work
- Accessing protected routes without login
- Submitting forms without CSRF tokens
- Regular users accessing admin features
- Weak passwords (if validation added)

## Troubleshooting

### Issue: "Address already in use"
```bash
lsof -ti:5010 | xargs kill -9
```

### Issue: "Cannot access database"
```bash
FLASK_APP=run.py flask init-db
```

### Issue: "No admin users"
```bash
FLASK_APP=run.py flask create-admin admin admin@company.com --password AdminPass123
```

### Issue: "CSRF token errors"
- Clear browser cookies
- Restart server
- Check for JavaScript errors in browser console

## Success Criteria

✅ **Authentication works** if:
- Unauthenticated users are redirected to login
- Login works with valid credentials
- All existing features work after login
- Admin features are restricted to admins
- Logout works correctly
- CLI commands work
- Estonian language is preserved

🎉 **Integration is successful!**

## Next Steps

1. **Production Setup:**
   - Set strong SECRET_KEY
   - Configure production database
   - Set up SSL/HTTPS
   - Disable debug mode

2. **User Training:**
   - Create user accounts
   - Show login/logout process
   - Explain admin features

3. **Backup:**
   - Backup user data
   - Document admin procedures
   - Set up regular backups

---

*This verification should take ~10 minutes to complete thoroughly.*