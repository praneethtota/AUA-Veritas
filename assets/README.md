# AUA-Veritas Assets

This directory contains app icons and DMG background needed for packaging.

## Required files (must be created before building)

### macOS
- `icon.icns` — App icon, 1024×1024px source, converted to .icns
  Generate from a PNG:
  ```
  mkdir icon.iconset
  sips -z 16 16 icon.png --out icon.iconset/icon_16x16.png
  sips -z 32 32 icon.png --out icon.iconset/icon_16x16@2x.png
  sips -z 32 32 icon.png --out icon.iconset/icon_32x32.png
  sips -z 64 64 icon.png --out icon.iconset/icon_32x32@2x.png
  sips -z 128 128 icon.png --out icon.iconset/icon_128x128.png
  sips -z 256 256 icon.png --out icon.iconset/icon_128x128@2x.png
  sips -z 256 256 icon.png --out icon.iconset/icon_256x256.png
  sips -z 512 512 icon.png --out icon.iconset/icon_256x256@2x.png
  sips -z 512 512 icon.png --out icon.iconset/icon_512x512.png
  sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
  iconutil -c icns icon.iconset
  ```

- `dmg-background.png` — DMG window background, 1080×540px
  Can be a simple gradient or branded image. If missing, DMG uses default background.

- `tray-icon.png` — System tray icon, 16×16 or 22×22px, preferably white/template style

### Windows
- `icon.ico` — Windows app icon

The build-mac.sh script generates simple placeholder icons if these are missing,
so you can do a first test build without them.
