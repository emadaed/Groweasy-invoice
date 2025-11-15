# core/middleware.py
from flask import g, request
import secrets

def security_headers(app):
    @app.before_request
    def set_nonce():
        g.nonce = secrets.token_urlsafe(16)

    @app.after_request
    def add_security_headers(response):
        csp = [
            "default-src 'self'",
            f"script-src 'self' 'nonce-{g.nonce}' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "img-src 'self' data: blob: https:",
            "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com fonts.gstatic.com",
            "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "frame-ancestors 'none'",
            "worker-src 'self'"
        ]
        response.headers['Content-Security-Policy'] = '; '.join(csp)
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.after_request
    def add_cache_headers(response):
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return response
