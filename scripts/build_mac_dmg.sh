#!/usr/bin/env bash
# Build dist/HealthAssessmentPet.app and a drag-to-Applications disk image.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "scripts/build_mac_dmg.sh only runs on macOS." >&2
  exit 1
fi

echo "==> [1/4] Install packaging tools into the user site (pyinstaller, rumps, openpyxl)..."
python3 -m pip install --user pyinstaller rumps openpyxl

echo "==> [2/4] Generate the .icns app icon and the menu-bar icon..."
python3 scripts/generate_mac_assets.py

echo "==> [3/4] Build HealthAssessmentPet.app with PyInstaller..."
python3 -m PyInstaller --noconfirm --clean --windowed --noupx \
  --name "HealthAssessmentPet" \
  --icon "assets/AppIcon.icns" \
  --osx-bundle-identifier "com.songhangze.healthassessment" \
  --paths "scripts" \
  --add-data "assets:assets" \
  --add-data "prompts:prompts" \
  --add-data "standards:standards" \
  --add-data "workflows:workflows" \
  --hidden-import "health_api_server" \
  --hidden-import "score_checkin" \
  --hidden-import "mac_dashboard_ui" \
  --hidden-import "openpyxl" \
  --hidden-import "rumps" \
  --collect-all "rumps" \
  --collect-all "objc" \
  scripts/mac_menubar_pet.py

PLIST="dist/HealthAssessmentPet.app/Contents/Info.plist"
if [[ -f "$PLIST" ]]; then
  /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
  /usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :NSHighResolutionCapable true" "$PLIST"
fi
codesign --force --deep --sign - "dist/HealthAssessmentPet.app" >/dev/null 2>&1 || true

echo "==> [4/4] Create a drag-install disk image with hdiutil..."
DMG_STAGING="dist/dmg_staging"
DMG_OUT="dist/HealthAssessmentPet.dmg"
rm -rf "$DMG_STAGING" "$DMG_OUT"
mkdir -p "$DMG_STAGING"
cp -R "dist/HealthAssessmentPet.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"
hdiutil create \
  -volname "Health Assessment Pet" \
  -srcfolder "$DMG_STAGING" \
  -ov -format UDZO \
  "$DMG_OUT"
rm -rf "$DMG_STAGING"
echo "DMG ready: $(pwd)/$DMG_OUT"
