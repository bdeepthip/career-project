"""
Shared Flask extensions, created once and connected to the app in
create_app(). Kept in their own module so any blueprint can import them.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

# Counts requests per visitor IP address. Limits are set on the routes
# that need them (login, sign-up, password reset, the email webhook).
limiter = Limiter(get_remote_address)
