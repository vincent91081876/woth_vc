# Third-party data notices

## codeaid/woth-toolbox map and animal data

`data/need_zones.json` is derived from map and animal configuration files in:

- Project: https://github.com/codeaid/woth-toolbox
- Source revision: `a0a73f84cd7506b4a813ec3b79e36f363d12655a`
- Revision date: 2026-03-28
- Upstream license: GNU General Public License v3.0 (GPL-3.0)
- License text: https://www.gnu.org/licenses/gpl-3.0.html

The build script converts the upstream normalized image coordinates to the
world-coordinate calibration used by this application, normalizes a small
number of species slugs, and attaches Traditional Chinese area/habitat labels.
The transformed data remains attributed to the upstream project under
GPL-3.0. Elkcrest Island is not included because the referenced upstream
revision has no need-zone data for that reserve.

The software's use of this data does not imply endorsement by codeaid,
Nine Rocks Games, THQ Nordic, or the Way of the Hunter project.

## Toolbox map imagery (toolbox.byteset.io)

`web/maps/*.webp` (v4.0.5+) are composites built by `tools/build_maps.py` from the
`base.webp`, `normal.webp` and `mask.webp` images published by the Way of the
Hunter Toolbox at https://toolbox.byteset.io/maps/. The underlying game art
belongs to Expansive Worlds / Nine Rocks Games / THQ Nordic; the Toolbox site
has no published license for its image assets, so they are included here for
personal, non-commercial use only. Please remove them if the rights holders ask.
This use does not imply endorsement by the Toolbox authors or the game's publisher.

## pyooz / ooz decompressor

The Windows launcher installs the bundled `pyooz` wheel when Oodle-compressed
WOTH saves require it.

- Project: https://github.com/zao/pyooz
- Underlying decoder: https://github.com/powzix/ooz
- License: GNU General Public License v3.0 or later

This decoder is used only to decompress save bytes in memory. The scanner still
opens the original game save read-only and never writes decompressed data back
to it.