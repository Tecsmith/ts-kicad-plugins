# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Release tags currently use calendar dates, such as `2026.05.11`, instead of Semantic Versioning.

## [Unreleased]

### Added

- Round Zone Rule now offers a selector for enabled copper layers.
- The README now includes installation, packaging, and compatibility instructions.

### Changed

- Package metadata restricts compatibility to KiCad 10.0.x and declares the legacy Python interface.
- Python 3 now builds package archives without platform-specific `sed` or `grep` commands.
- Local package builds no longer require `GITHUB_ENV` and preserve existing archives for other versions.

### Fixed

- Teardrops now registers with KiCad and appears alongside the other plugins.
- Teardrops reads via and pad sizes for each copper layer and excludes vias from the track list.
- Existing teardrops on one layer no longer suppress teardrops on another layer.
- Polygon teardrops now use persistent named groups so removal preserves unrelated artwork. Keep these groups intact for automatic removal.
  Remove older, unmarked polygon teardrops manually.
- FabText now includes custom footprint fields on F.Fab and B.Fab.
- FabText applies offsets and text angles in footprint coordinates for rotated footprints.
- FabText saves thickness in millimeters when automatic thickness is enabled, including when the dialog uses inches or mils.
- RoundFillZone and RoundZoneRule now use selected tracks to calculate the default center and radius.
- Package builds reject invalid version numbers and exclude Python bytecode caches.
- Release tags pass through environment variables and quoted arguments to prevent shell interpretation.

[Unreleased]: https://github.com/Tecsmith/ts-kicad-plugins/compare/2026.05.11...HEAD
