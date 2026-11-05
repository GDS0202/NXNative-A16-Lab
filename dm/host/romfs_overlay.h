// Read-only overlays. Resolve every component with openat/O_NOFOLLOW so a mod
// cannot escape its root through '..', a symlink, or a special file.
#pragma once
int dm_romfs_overlay_open(const char *relative);
int dm_romfs_overlay_candidate(const char *relative);
