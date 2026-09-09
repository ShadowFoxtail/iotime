#!/usr/bin/env bash

set -euo pipefail

APP_NAME="iotime"

SOURCE_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/iotime"
VENV_DIR="$DATA_DIR/venv"
BIN_DIR="$HOME/bin"
LAUNCHER="$BIN_DIR/iotime"

echo "Installing $APP_NAME..."

mkdir -p "$DATA_DIR"
mkdir -p "$BIN_DIR"

echo "Copying application..."
cp "$SOURCE_DIR/iotime.py" "$DATA_DIR/iotime.py"

echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

echo "Installing dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install \
    -r "$SOURCE_DIR/requirements.txt"

echo "Creating launcher..."

cat > "$LAUNCHER" <<LAUNCHER_EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" \
     "$DATA_DIR/iotime.py" "\$@"
LAUNCHER_EOF

chmod +x "$LAUNCHER"

echo
echo "iotime installed successfully."
echo
echo "Launcher:"
echo "  $LAUNCHER"
echo
echo "Application:"
echo "  $DATA_DIR/iotime.py"
echo

if command -v iotime >/dev/null 2>&1; then
    echo "Try:"
    echo "  iotime --forecast"
else
    echo "NOTE: $BIN_DIR does not appear to be in your PATH."
    echo "Add it to your shell PATH, then run:"
    echo "  iotime --forecast"
fi
