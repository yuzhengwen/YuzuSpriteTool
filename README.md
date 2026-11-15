# Yuzu Sprite Tool

Desktop app (PySide6 + Pillow) for slicing sprite sheets apart (**Unpack**) and packing sprites into a sheet (**Pack**).

## Run from source

```
run.bat
```

Creates `.venv` on first run. Nothing is installed globally.

## Build the standalone exe

```
build.bat            smoke test, then build
build.bat run        smoke test, build, then launch the exe
build.bat fast       skip the smoke test
build.bat fast run   skip the test and launch afterwards
```

Output: `dist\YuzuSpriteTool.exe`. It is a single file with no Python needed, so you can copy it anywhere.

The pipeline:
1. Creates or reuses `.venv`.
2. Installs `requirements-dev.txt` (app deps + PyInstaller).
3. Runs `tests\smoke_test.py` offscreen. A failing test stops the build.
4. Runs PyInstaller with `YuzuSpriteTool.spec`. It first closes any running copy of the exe so the file can be replaced.

After changing code, run `build.bat run` again.

## Files

| File | What it is |
|---|---|
| `main.py` | The UI (both tabs, preview popup) |
| `sprite_core.py` | Slicing and packing logic, no UI |
| `tests/smoke_test.py` | Core checks + offscreen UI run; screenshots go to `tests/out/` |
| `YuzuSpriteTool.spec` | PyInstaller recipe (excludes unused Qt modules to keep the exe small) |
| `tools/make_icon.py` | Generates `assets/icon.ico`; delete the .ico to regenerate |
