# Versioning and compatibility

Xenari uses semantic versioning for the surfaces intended for other tools:

- `xenari.Xenari`, `xenari.db.XenariDB`, and documented public methods.
- The `xenari` console command and documented command options.
- Packaged SQLite columns and generated dictionary fields.
- The shared Python/browser translator fixture contract.
- The versioned generated runtime-table schema and field meanings.

Patch releases fix behavior without intentionally changing those contracts.
Minor releases add compatible commands, fields, or grammar support. Major
releases may remove deprecated interfaces or change established output.

Private underscore-prefixed helpers and explicitly generated files are not
stable APIs. Canon roots are language data: corrections are recorded in the
changelog even when they do not require a package-major release.
