#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
output="$(realpath -m "${1:?Provide an output directory under /tmp/norvi-office-tests}")"
case "$output" in /tmp/norvi-office-tests/*) ;; *) exit 2 ;; esac
mkdir -p "$output"
cc -std=c11 -Wall -Wextra -Werror -O2 "$root/test_glass.c" -o "$output/test-glass" \
    $(pkg-config --cflags --libs cairo) -lm
"$output/test-glass"
cc -std=c11 -Wall -Wextra -Werror -O2 -fPIC -shared \
    "$root/header.c" -o "$output/libnorvi-office-header.so" \
    $(pkg-config --cflags --libs gtk+-3.0 gmodule-2.0)
printf '%s\n' "$output/libnorvi-office-header.so"
cc -std=c11 -Wall -Wextra -Werror -O2 "$root/test_menu.c" -o "$output/test-menu" \
    $(pkg-config --cflags --libs gtk+-3.0 gmodule-2.0)
"$output/test-menu"
/usr/bin/python3 -m unittest discover -s "$root" -p test_routing.py -v
