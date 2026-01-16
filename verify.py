import sys
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("🚀 PRODUCTION VERIFICATION CHECKLIST")
print("=" * 60)

checks = [
    ("Python 3.12.10", sys.version.startswith("3.12.10")),
    (".env file exists", os.path.exists(".env")),
    ("Database URL set", bool(os.getenv("DATABASE_URL"))),
    ("Redis URL", os.getenv("REDIS_URL", "memory://") != ""),
    ("Secret key", bool(os.getenv("SECRET_KEY"))),
]

all_passed = True
for check, passed in checks:
    status = "✅" if passed else "❌"
    print(f"{status} {check}")
    if not passed:
        all_passed = False

print("\n" + "=" * 60)
if all_passed:
    print("🎉 READY FOR PRODUCTION DEPLOYMENT!")
    print("Run: git push origin main")
else:
    print("⚠️ Some checks failed. Fix them before deployment.")
print("=" * 60)
