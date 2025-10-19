#!/usr/bin/env bash
set -e
echo "Running post-deploy: ensuring system libs for WeasyPrint are present"
if command -v yum >/dev/null 2>&1; then
  sudo yum -y install cairo cairo-devel pango pango-devel libffi-devel gdk-pixbuf2 libjpeg-turbo-devel freetype-devel || true
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf -y install cairo cairo-devel pango pango-devel libffi-devel gdk-pixbuf2 libjpeg-turbo-devel freetype-devel || true
else
  echo "No yum/dnf available - please ensure system dependencies for WeasyPrint are installed."
fi

# upgrade pip in virtualenv if present
if [ -n "$EB_PYTHON_VENV" ]; then
  source "$EB_PYTHON_VENV/bin/activate"
  pip install --upgrade pip setuptools wheel
  deactivate
fi
echo "Post-deploy WeasyPrint deps step completed."
