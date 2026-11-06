# Project operations manual

Revision 1

Use the following instructions when the recorded conditions apply.

## check-git-tree

Before publishing a source ZIP, reconstruct each upstream Git tree from the archive entries and compare it to the pinned tree. Include paths, file bytes, executable modes and symbolic links.

Applies when delivery = source-zip, task = publish.
Practice evidence (opsbook-first-zip): Launch incident, 6 November 2026. The v0.1.0 packer created new ZIP entries without preserving Git mode 100755. The pinned pstack tree includes executable scripts.

