# final_fixes.py - COMPLETE FIXES FOR ALL ISSUES
import os
import sys

print("🎯 APPLYING FINAL FIXES...")

# ============================================================================
# 1. FIX TEMPLATES (data.items vs data.get('items', []))
# ============================================================================
template_fixes = {
    'templates/invoice_pdf.html': [
        ("{% for item in data.items %}", "{% for item in data.get('items', []) %}"),
        ("{{ data.items|length }}", "{{ data.get('items', [])|length }}")
    ],
    'templates/purchase_order_pdf.html': [
        ("{% for item in data.items %}", "{% for item in data.get('items', []) %}"),
        ("{{ data.items|length }}", "{{ data.get('items', [])|length }}")
    ],
    'templates/po_preview.html': [
        ("data.items", "data.get('items', [])")
    ],
    'templates/invoice_preview.html': [
        ("data.items", "data.get('items', [])")
    ]
}

for template_file, replacements in template_fixes.items():
    if os.path.exists(template_file):
        with open(template_file, 'r') as f:
            content = f.read()

        original_content = content
        for old, new in replacements:
            content = content.replace(old, new)

        if content != original_content:
            with open(template_file, 'w') as f:
                f.write(content)
            print(f"✅ Fixed {template_file}")

# ============================================================================
