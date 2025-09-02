"""Simple authentication flow checks using Flask test client.
Run: python auth_check.py
Outputs pass/fail for core login/password behaviors.
"""
import re
import uuid
from contextlib import contextmanager
from app import app, load_users, users

@contextmanager
def client():
    with app.test_client() as c:
        yield c

def assert_true(cond, msg):
    if cond:
        print(f"[PASS] {msg}")
    else:
        print(f"[FAIL] {msg}")

def main():
    # Unique test user
    test_username = f"testuser_{uuid.uuid4().hex[:8]}"
    test_password = "TestPass123!"
    with client() as c:
        # 1. Register new user
        resp = c.post('/register', data={'username': test_username, 'password': test_password}, follow_redirects=False)
        assert_true(resp.status_code in (302,303), 'Registration redirects (success)')
        load_users()
        created = next((u for u in users if u['username'].lower() == test_username.lower()), None)
        if not created:
            print(f"[DEBUG] Current users: {[u['username'] for u in users]}")
        assert_true(created is not None, 'User created and present in users.json')
        if created:
            ph = created.get('password_hash', '')
            assert_true(ph.startswith('scrypt:'), 'Password stored as scrypt hash')
        # 2. Login with correct password
        resp = c.post('/login', data={'username': test_username, 'password': test_password}, follow_redirects=False)
        assert_true(resp.status_code in (302, 303), 'Successful login returns redirect')
        location = resp.headers.get('Location', '')
        assert_true('/tasks' in location, 'Login redirects to tasks_page')
        # 3. Login with wrong password
        resp_bad = c.post('/login', data={'username': test_username, 'password': 'WrongPass'}, follow_redirects=True)
        body = resp_bad.get_data(as_text=True)
        assert_true('Invalid username or password.' in body, 'Invalid password shows flash message')
        # 4. Case sensitivity check
        resp_case = c.post('/login', data={'username': test_username.upper(), 'password': test_password}, follow_redirects=True)
        body_case = resp_case.get_data(as_text=True)
        if 'Invalid username or password.' in body_case:
            print('[FAIL] Case-insensitive login expected but failed.')
        else:
            print('[PASS] Case-insensitive login working.')
        # 5. Logout flow
        # First login again to set session
        c.post('/login', data={'username': test_username, 'password': test_password}, follow_redirects=False)
        resp_logout = c.get('/logout', follow_redirects=False)
        assert_true(resp_logout.status_code in (302, 303), 'Logout returns redirect')
        assert_true('/login' in resp_logout.headers.get('Location', ''), 'Logout redirects to login page')
        # 6. Password reset flow
        # Request token
        resp_fp = c.post('/forgot', data={'username': test_username}, follow_redirects=True)
        body_fp = resp_fp.get_data(as_text=True)
        import re
        m = re.search(r'<code[^>]*>([A-Za-z0-9_\-]+)</code>', body_fp)
        if m:
            token = m.group(1)
            assert_true(len(token) > 10, 'Reset token length reasonable')
            # Use token to reset password
            new_pw = 'NewPass123!'
            resp_reset = c.post(f'/reset/{token}', data={'password': new_pw, 'confirm_password': new_pw}, follow_redirects=True)
            assert_true('Password reset successful' in resp_reset.get_data(as_text=True), 'Password reset success message')
            # Login with new password
            resp_login_new = c.post('/login', data={'username': test_username, 'password': new_pw}, follow_redirects=False)
            assert_true(resp_login_new.status_code in (302,303), 'Login works with new password')
        else:
            assert_true(False, 'Reset token extracted')

    print('\nSummary: Review PASS/FAIL lines above. Consider adding rate limiting & complexity rules.')

if __name__ == '__main__':
    main()
