#include "glass_pixels.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { WIDTH = 80, HEIGHT = 100 };

static cairo_t *frame(void) {
    cairo_surface_t *surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, WIDTH, HEIGHT);
    cairo_t *context = cairo_create(surface);
    cairo_surface_destroy(surface);
    cairo_set_source_rgb(context, 44.0 / 255, 44.0 / 255, 44.0 / 255);
    cairo_paint(context);
    return context;
}

static uint32_t *row(cairo_t *context, int y) {
    cairo_surface_t *surface = cairo_get_target(context);
    cairo_surface_flush(surface);
    return (uint32_t *)(cairo_image_surface_get_data(surface) +
        y * cairo_image_surface_get_stride(surface));
}

static void atomic_frame_and_ink(void) {
    cairo_t *context = frame();
    /* Include dark saturated indicators and black input-field ink. */
    uint32_t indicators[] = {0xffffffff, 0xff800000, 0xff008000, 0xff000080,
        0xffffa000, 0xffc8c8c8, 0xff000000};
    for (unsigned i = 0; i < sizeof(indicators) / sizeof(*indicators); i++)
        row(context, 8)[8 + i] = indicators[i];
    uint32_t document[WIDTH * 80];
    memcpy(document, row(context, 20), sizeof(document));
    GlassPaint paint;
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_APPLIED);
    assert(paint.pixels > 0 && paint.x == 0 && paint.y == 0 && paint.edge == 20);
    assert(row(context, 0)[0] == 0xb8202020);
    assert(memcmp(document, row(context, 20), sizeof(document)) == 0);
    for (unsigned i = 0; i < sizeof(indicators) / sizeof(*indicators); i++)
        assert(row(context, 8)[8 + i] == indicators[i]);
    /* A stale/composed source cannot be multiplied twice. */
    uint32_t first[WIDTH * HEIGHT];
    memcpy(first, row(context, 0), sizeof(first));
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_SOURCE_ALPHA);
    assert(memcmp(first, row(context, 0), sizeof(first)) == 0);
    cairo_destroy(context);
}

static void growing_and_shrinking_frames(void) {
    const int edges[] = {20, 40, 12, 35, 8};
    cairo_t *context = frame();
    for (unsigned i = 0; i < sizeof(edges) / sizeof(*edges); i++) {
        /* Reuse the actual image, clearing the preceding frame's alpha by
         * repainting an opaque source, as the full-frame GTK path requires. */
        cairo_set_source_rgb(context, 44.0 / 255, 44.0 / 255, 44.0 / 255);
        cairo_paint(context);
        /* Fictional document with both light and dark pixels right at edge. */
        for (int y = edges[i]; y < HEIGHT; y++)
            for (int x = 0; x < WIDTH; x++)
                row(context, y)[x] = x % 2 ? 0xfffefefe : 0xff080810;
        uint32_t before[WIDTH * HEIGHT];
        memcpy(before, row(context, 0), sizeof(before));
        GlassPaint paint;
        assert(glass_compose(context, WIDTH, HEIGHT, edges[i], &paint) == GLASS_APPLIED);
        assert(memcmp(before + WIDTH * edges[i], row(context, edges[i]),
            (HEIGHT - edges[i]) * WIDTH * 4) == 0);
    }
    cairo_destroy(context);
}

static void partial_damage_and_unsupported(void) {
    cairo_t *context = frame();
    uint32_t before[WIDTH * HEIGHT];
    memcpy(before, row(context, 0), sizeof(before));
    cairo_rectangle(context, 0, 0, WIDTH, HEIGHT - 1);
    cairo_clip(context);
    GlassPaint paint;
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_CLIP);
    assert(memcmp(before, row(context, 0), sizeof(before)) == 0);
    cairo_reset_clip(context);
    cairo_scale(context, 2, 2);
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_TRANSFORM);
    cairo_identity_matrix(context);
    cairo_translate(context, 0.5, 0);
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_TRANSFORM);
    cairo_identity_matrix(context);
    cairo_surface_set_device_scale(cairo_get_target(context), 2, 2);
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_TRANSFORM);
    assert(memcmp(before, row(context, 0), sizeof(before)) == 0);
    cairo_destroy(context);
    cairo_surface_t *recording = cairo_recording_surface_create(CAIRO_CONTENT_COLOR_ALPHA, NULL);
    context = cairo_create(recording);
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_TARGET);
    cairo_destroy(context);
    cairo_surface_destroy(recording);
    cairo_surface_t *rgb = cairo_image_surface_create(CAIRO_FORMAT_RGB24, WIDTH, HEIGHT);
    context = cairo_create(rgb);
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_FORMAT);
    cairo_destroy(context);
    cairo_surface_destroy(rgb);
}

static void transformed_surface_and_disjoint_clip(void) {
    cairo_t *context = frame();
    cairo_surface_t *surface = cairo_get_target(context);
    cairo_surface_set_device_offset(surface, 3, 2);
    cairo_translate(context, 4, 5);
    cairo_set_source_rgb(context, 0.2, 0.2, 0.2);
    cairo_rectangle(context, 0, 0, 20, 60);
    cairo_fill(context);
    assert(row(context, 7)[7] == 0xff333333);
    cairo_rectangle(context, 0, 0, 20, 30);
    cairo_rectangle(context, 0, 30, 20, 30);
    cairo_clip(context);
    uint32_t before[WIDTH * HEIGHT];
    memcpy(before, row(context, 0), sizeof(before));
    GlassPaint paint;
    assert(glass_compose(context, 20, 60, 20, &paint) == GLASS_APPLIED);
    assert(paint.x == 7 && paint.y == 7 && paint.width == 20 && paint.edge == 20);
    for (int y = 0; y < HEIGHT; y++)
        for (int x = 0; x < WIDTH; x++)
            if (x < 7 || x >= 27 || y < 7 || y >= 27)
                assert(before[y * WIDTH + x] == row(context, y)[x]);
    cairo_destroy(context);
}

static void rejection_does_not_restore_a_reused_buffer(void) {
    cairo_t *context = frame();
    GlassPaint paint;
    assert(glass_compose(context, WIDTH, HEIGHT, 40, &paint) == GLASS_APPLIED);
    /* A new ATK edge with an old image is unsafe even inside the client.
     * Rejection leaves previously composed rows translucent. This reproduces
     * the adapter blocker; it is not an opaque-fallback acceptance check. */
    assert(glass_compose(context, WIDTH, HEIGHT, 20, &paint) == GLASS_SOURCE_ALPHA);
    for (int y = 20; y < 40; y++)
        assert(row(context, y)[0] >> 24 == 184);
    cairo_destroy(context);
    puts("Known blocker reproduced: rejection does not clean up a reused glass buffer");
}

int main(void) {
    atomic_frame_and_ink();
    growing_and_shrinking_frames();
    partial_damage_and_unsupported();
    transformed_surface_and_disjoint_clip();
    rejection_does_not_restore_a_reused_buffer();
    assert(strcmp(glass_reason(GLASS_APPLIED), "applied") == 0);
    puts("Client glass: atomic document/ink, resize, repeated draw, clip, surface and transform checks passed");
    return 0;
}
