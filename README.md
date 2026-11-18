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

## Project layout

```
main.py                     launcher (also the PyInstaller entry point)
sprite_tool/
  app.py                    startup: QApplication, theme, icon, main window
  resources.py              finds bundled files (source or exe)
  core/                     image logic: Pillow only, no Qt
    geometry.py             Rect
    image_io.py             loading images, supported extensions
    naming.py               numbered file names, natural sort
    slicing.py              SliceSettings, compute_cells, slice_sheet
    packing.py              PackSettings, pack_sprites, pack_metadata
    editing.py              SpriteEdit (crop + resize), apply_edit: non-destructive
    animation.py            playback stepping (loop / ping-pong / once), compose_frames
  ui/
    main_window.py          the window: hosts both tabs and wires them together
    theme.py                all colors, palette and stylesheet
    qt_image.py             Pillow to Qt conversion, thumbnails, checkerboard
    file_dialogs.py         open/save pickers and saving many files
    prefs.py                remembered folder, window size, last tab
    forms/                  settings panels (emit `changed`, return their values)
      slice_form.py         "How to slice"
      pack_form.py          "Layout"
      crop_form.py          sprite editor: "Crop"
      resize_form.py        sprite editor: "Resize"
    dialogs/
      preview_dialog.py     full-size view of a sliced sprite
      sprite_editor_dialog.py  crop/resize a sprite in a sprite list
    panels/                 building blocks shared by several tabs
      sheet_slicer_panel.py sheet view + "How to slice" (Unpack, Animate)
      sprite_list_panel.py  ordered, editable sprite list (Pack, Animate)
    tabs/
      unpack_tab.py         sheet on the left, sliced sprites on the right
      pack_tab.py           ordered sprite list on the left, packed sheet on the right
      animate_tab.py        sprites or sheet on the left, animation preview on the right
    widgets/                reusable widgets with no tab-specific logic
      image_view.py         zoom/pan viewer with grid and selection overlays
      crop_view.py          image view where dragging draws a crop area
      pack_entry_delegate.py  sprite list rows: clickable thumbnail, Edit and revert buttons
      frame_strip.py        animation filmstrip that highlights the current frame
      playback_bar.py       play/pause, step, speed and loop-mode controls
      transport_icons.py    media icons drawn in code (font-independent)
      segmented.py          joined toggle buttons (Sprites | Sprite sheet)
      zoom_bar.py, sprite_delegate.py, sprite_order_list.py, placeholder.py, factory.py
tests/
  test_core.py              pure logic checks
  smoke_test.py             core checks + offscreen UI run (screenshots in tests/out/)
tools/make_icon.py          generates assets/icon.ico
YuzuSpriteTool.spec         PyInstaller recipe
```

Dependencies only point one way: `ui` uses `core`, and `core` never imports Qt. To add a slicing or packing feature, add it to `core` and test it in `tests/test_core.py`, then expose it in the matching form.
