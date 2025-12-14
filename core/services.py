# core/services.py
from flask import current_app, render_template
from celery import Celery
import redis
import json
from .invoice_logic import prepare_invoice_data
from .qr_engine import make_qr_with_logo as generate_simple_qr  # Use existing, but no logo
from sqlalchemy import text

class InvoiceService:
    def __init__(self, user_id):
        self.user_id = user_id
        self.redis_client = redis.from_url(current_app.config['REDIS_URL'])
        self.data = None
        self.celery = Celery(current_app.name, broker=self.redis_client.url)

    def process(self, form_data, files, action='preview'):
        self.data = prepare_invoice_data(form_data, files)
        self.save_state()  # Redis + DB

        if action == 'preview':
            return self.generate_preview_async()
        elif action == 'download':
            return self.generate_download()

    def save_state(self):
        # Save to Redis (fast)
        self.redis_client.setex(f"invoice:{self.user_id}", 3600, json.dumps(self.data))
        # Save to DB (persistent)
        with DB_ENGINE.connect() as conn:
            conn.execute(text("INSERT OR REPLACE INTO pending_invoices (user_id, invoice_data) VALUES (:u, :d)"),
                        {'u': self.user_id, 'd': json.dumps(self.data)})
            conn.commit()

    def get_state(self):
        cached = self.redis_client.get(f"invoice:{self.user_id}")
        if cached:
            return json.loads(cached)
        # Fallback to DB
        with DB_ENGINE.connect() as conn:
            result = conn.execute(text("SELECT invoice_data FROM pending_invoices WHERE user_id = :u"), {'u': self.user_id}).fetchone()
            return json.loads(result[0]) if result else {}

    def generate_preview_async(self):
        task = self.celery.send_task('tasks.generate_preview', args=[self.user_id, self.data])
        return {'task_id': task.id, 'status': 'queued'}  # Poll in route

    def generate_download(self):
        # Sync for download
        qr_b64 = generate_simple_qr(self.data, logo_b64=None)  # Pass None to mute logo
        html = render_template('invoice_pdf.html', data=self.data, preview=False,
                              custom_qr_b64=qr_b64, fbr_qr_code=None,  # Mute FBR
                              fbr_compliant=False, currency_symbol='Rs.')
        pdf_bytes = generate_pdf(html, current_app.root_path)
        return Response(pdf_bytes, mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename=invoice_{self.data["invoice_number"]}.pdf'})
