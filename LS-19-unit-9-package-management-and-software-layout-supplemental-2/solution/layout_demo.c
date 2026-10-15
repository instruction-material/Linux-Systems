#include <stdio.h>
#include <string.h>

#ifndef APP_VERSION
#error APP_VERSION must be supplied by the build command
#endif

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts(APP_VERSION);
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "--status") == 0) {
        printf("manual-source build version=%s\n", APP_VERSION);
        return 0;
    }
    fputs("usage: layout-demo --version|--status\n", stderr);
    return 2;
}
