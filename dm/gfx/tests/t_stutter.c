#include "../nvn/nvn_stutter.h"
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static void *producer(void *unused) {
    uintptr_t id = (uintptr_t)unused;
    for (uint64_t i = 1; i <= 4000; i++) {
        nvn_stutter_sample s = {.frame = id * 4000 + i, .timestamp_ns = 1000000 + i, .frame_ms = 16.666667, .gpu_ms = -1};
        nvn_stutter_frame(&s); nvn_stutter_present(s.frame, s.frame, s.timestamp_ns);
    }
    return NULL;
}
int main(int argc, char **argv) {
    char dir[] = "/tmp/nx-stutter-XXXXXX"; assert(mkdtemp(dir)); assert(!chdir(dir));
    setenv("DM_STUTTER", "0", 1); assert(!nvn_stutter_enabled());  // pre-launch queries must not initialize
    int on = argc > 1 && !strcmp(argv[1], "on"); setenv("DM_STUTTER", on ? "1" : "0", 1);
    assert(nvn_stutter_start() == on); assert(nvn_stutter_enabled() == on);
    if (!on) { nvn_stutter_present(1, 1, 1); nvn_stutter_stop(); assert(access("stutter.jsonl", F_OK)); }
    else {
        pthread_t p[4]; for (uintptr_t i = 0; i < 4; i++) assert(!pthread_create(&p[i], NULL, producer, (void *)i));
        for (unsigned i = 0; i < 4; i++) assert(!pthread_join(p[i], NULL));
        nvn_stutter_system(1, 100, 200, 0, 0); nvn_stutter_boundary(2); nvn_stutter_stop(); nvn_stutter_stop();
        struct stat st; assert(!stat("stutter.jsonl", &st)); assert(st.st_size > 0 && st.st_size <= 8192);
        FILE *f = fopen("stutter.jsonl", "r"); assert(f); char line[2048]; int capped = 0;
        while (fgets(line, sizeof line, f)) { assert(strchr(line, '\n')); if (strstr(line, "\"capped\":true")) capped = 1; }
        fclose(f); assert(capped); unlink("stutter.jsonl");
    }
    assert(!chdir("/tmp")); assert(!rmdir(dir)); puts("Bounded trace: enable/disable, concurrent producers, cap and shutdown PASS");
    return 0;
}
