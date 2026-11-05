#include "romfs_overlay.h"
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int under(const char *root, const char *relative) {
    if (!root || !*root || !relative) return -1;
    while (*relative == '/') relative++;
    if (!*relative || strlen(relative) > 2048) return -1;
    int fd = open(root, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return -1;
    char path[2049]; strcpy(path, relative); char *save = NULL;
    for (char *part = strtok_r(path, "/", &save); part;) {
        if (!strcmp(part, ".") || !strcmp(part, "..") || strchr(part, ':') || strchr(part, '\\')) { close(fd); return -1; }
        char *next = strtok_r(NULL, "/", &save);
        int child = openat(fd, part, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK | (next ? O_DIRECTORY : 0));
        close(fd); if (child < 0) return -1; fd = child; part = next;
    }
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode)) { close(fd); return -1; }
    return fd;
}
static int under_list(const char *roots, const char *relative) {
    if (!roots) return -1;
    for (const char *part = roots; *part;) {
        const char *end = strchr(part, ':');
        size_t n = end ? (size_t)(end - part) : strlen(part);
        if (n && n < 2049) {
            char root[2049]; memcpy(root, part, n); root[n] = 0;
            int fd = under(root, relative); if (fd >= 0) return fd;
        }
        if (!end) break;
        part = end + 1;
    }
    return -1;
}
int dm_romfs_overlay_candidate(const char *relative) {
    if (!relative) return 0;
    if (getenv("DM_ROMFS_MODS") || getenv("DM_ROMFS_OVERLAY")) return 1;
    while (*relative == '/') relative++;
    return getenv("DM_CONTROLLER_MODS_ROOT") && (!strncmp(relative, "Font/", 5) || !strcmp(relative, "Pack/Bootup.pack"));
}
int dm_romfs_overlay_open(const char *relative) {
    if (!dm_romfs_overlay_candidate(relative)) return -1;
    // Explicit user mods take priority; automatic controller assets are separate.
    int fd = under_list(getenv("DM_ROMFS_MODS"), relative);
    if (fd < 0) fd = under_list(getenv("DM_ROMFS_OVERLAY"), relative);
    return fd >= 0 ? fd : under(getenv("DM_CONTROLLER_MODS_ROOT"), relative);
}
