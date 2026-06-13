#!/bin/bash
set -e

pip install -r requirements.txt

# ginza 5.2.0 ships with split_mode = null in its config, which confection 1.3+
# rejects. Patch it to the effective default value "C".
python3 - <<'EOF'
import pathlib, site

for d in site.getsitepackages():
    cfg = pathlib.Path(d) / "ja_ginza" / "ja_ginza-5.2.0" / "config.cfg"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8")
        if "split_mode = null" in text:
            cfg.write_text(text.replace("split_mode = null", 'split_mode = "C"'), encoding="utf-8")
            print(f"Patched {cfg}")
        else:
            print(f"Already patched: {cfg}")
        break
else:
    print("WARNING: ja_ginza config.cfg not found — skipping patch")
EOF
