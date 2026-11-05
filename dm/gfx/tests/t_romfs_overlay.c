#include "../../host/romfs_overlay.h"
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

int main(void) {
    char path[] = "/tmp/nxnative-overlay-XXXXXX"; char *root = mkdtemp(path); assert(root);
    char file[512], link[512]; snprintf(file, sizeof file, "%s/glyph", root);
    int fd = open(file, O_WRONLY | O_CREAT | O_EXCL, 0600); assert(fd >= 0); assert(write(fd, "own", 3) == 3); close(fd);
    unsetenv("DM_ROMFS_MODS"); unsetenv("DM_ROMFS_OVERLAY"); unsetenv("DM_CONTROLLER_MODS_ROOT");
    assert(!dm_romfs_overlay_candidate("Font/glyph"));
    setenv("DM_ROMFS_MODS", root, 1); assert(dm_romfs_overlay_candidate("glyph"));
    fd = dm_romfs_overlay_open("/glyph"); assert(fd >= 0); char value[4] = {0}; assert(read(fd, value, 3) == 3); close(fd); assert(!strcmp(value, "own"));
    assert(dm_romfs_overlay_open("../glyph") < 0); assert(dm_romfs_overlay_open("./glyph") < 0);
    assert(dm_romfs_overlay_open("unknown/glyph") < 0); assert(dm_romfs_overlay_open("glyph/extra") < 0);
    snprintf(link, sizeof link, "%s/symlink", root); assert(!symlink(file, link));
    assert(dm_romfs_overlay_open("symlink") < 0); unlink(link);
    snprintf(link, sizeof link, "%s/pipe", root); assert(!mkfifo(link, 0600));
    assert(dm_romfs_overlay_open("pipe") < 0); unlink(link);
    unsetenv("DM_ROMFS_MODS"); setenv("DM_CONTROLLER_MODS_ROOT", "/unavailable", 1);
    char roots[1024]; snprintf(roots, sizeof roots, "/unavailable:%s:/also-unavailable", root);
    setenv("DM_ROMFS_OVERLAY", roots, 1);
    fd = dm_romfs_overlay_open("glyph"); assert(fd >= 0); close(fd);
    assert(dm_romfs_overlay_open(NULL) < 0);
    unsetenv("DM_ROMFS_OVERLAY"); setenv("DM_CONTROLLER_MODS_ROOT", root, 1);
    assert(!dm_romfs_overlay_candidate("Map/unrelated")); assert(dm_romfs_overlay_candidate("Font/glyph"));
    unlink(file); rmdir(root);
    puts("read-only overlays: correct reads, namespace filtering, traversal/symlink/FIFO rejection passed");
    return 0;
}
