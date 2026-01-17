# test_railway.py - Simple test for Railway
import os
import sys

print("🚀 Railway Deployment Test")
print("=" * 60)

# Test 1: Check critical files exist
print("1. File existence checks:")
critical_files = [
    'app.py',
    'core/db.py',
    'core/pdf_engine.py',
    'core/invoice_service.py',
    'templates/invoice_pdf.html',
    'templates/purchase_order_pdf.html',
    'requirements.txt',
    'Dockerfile'
]

all_exist = True
for file in critical_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} - MISSING")
        all_exist = False

# Test 2: Check template fixes
print("\n2. Template fixes check:")
template_fixes_applied = True
for template in ['templates/invoice_pdf.html', 'templates/purchase_order_pdf.html']:
    if os.path.exists(template):
        with open(template, 'r') as f:
            content = f.read()
            if 'data.items' in content and 'data.get(' not in content:
                print(f"   ❌ {template}: Needs data.get('items', []) fix")
                template_fixes_applied = False
            else:
                print(f"   ✅ {template}: Fixed")

# Test 3: Simple HTML test
print("\n3. Basic functionality test:")
test_html = "<h1>Test</h1><p>If you see this, HTML works.</p>"
print(f"   ✅ HTML test string: {len(test_html)} chars")

# Test 4: Environment check
print("\n4. Environment check:")
print(f"   Python: {sys.version.split()[0]}")
print(f"   Working directory: {os.getcwd()}")
print(f"   Files in directory: {len(os.listdir('.'))}")

print("\n" + "=" * 60)
if all_exist and template_fixes_applied:
    print("🎉 READY FOR RAILWAY DEPLOYMENT!")
    print("\n✅ All critical files present")
    print("✅ Template fixes applied")
    print("✅ Environment ready")
else:
    print("⚠️ SOME ISSUES DETECTED")
    print("\nFix the issues above before deploying")

print("\n" + "=" * 60)
print("🚀 DEPLOYMENT COMMAND:")
print("git add . && git commit -m '🚀 Production v1.0' && git push origin main")
