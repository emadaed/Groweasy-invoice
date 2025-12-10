# core/middleware.py
# Security middleware for Flask application
# Last updated: December 2025 - Turnstile removed

from flask import g, request
import secrets


def security_headers(app):
    """
    Add security headers to all responses.
    Implements CSP, XSS protection, and other security measures.
    """

    @app.before_request
    def set_nonce():
        """Generate a unique nonce for each request (for inline scripts)"""
        # Skip nonce for static files and service worker
        if not request.path.startswith('/static/') and request.path != '/sw.js':
            g.nonce = secrets.token_urlsafe(16)
        else:
            g.nonce = None

    @app.after_request
    def add_security_headers(response):
        """Add security headers to response"""

        # Content Security Policy
        if request.path == '/sw.js' or request.path.startswith('/static/'):
            # Relaxed CSP for static files
            csp = [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: blob: https:",
                "font-src 'self'",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "worker-src 'self'"
            ]
        else:
            # Full CSP for HTML pages - NO Cloudflare/Turnstile domains needed
            csp = [
                "default-src 'self'",
                f"script-src 'self' 'nonce-{g.nonce}' https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
                "img-src 'self' data: blob: https:",
                "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com fonts.gstatic.com",
                "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
                "frame-ancestors 'none'",
                "worker-src 'self'",
                "form-action 'self'",
                "base-uri 'self'"
            ]

        response.headers['Content-Security-Policy'] = '; '.join(csp)

        # Additional security headers
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(), payment=()'

        # HSTS - only in production
        if not request.host.startswith('localhost') and not request.host.startswith('127.0.0.1'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    @app.after_request
    def add_cache_headers(response):
        """Add appropriate cache headers"""
        if request.path.startswith('/static/'):
            # Cache static files for 1 year
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            # Don't cache dynamic content
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

        return response
