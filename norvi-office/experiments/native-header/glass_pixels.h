/* Client-buffer composition. No GTK or compositor state is used here. */
#ifndef NORVI_GLASS_PIXELS_H
#define NORVI_GLASS_PIXELS_H
#include <cairo.h>
#include <math.h>
#include <stdint.h>

typedef enum {
    GLASS_APPLIED, GLASS_GEOMETRY, GLASS_TARGET, GLASS_FORMAT,
    GLASS_TRANSFORM, GLASS_CLIP, GLASS_BOUNDS, GLASS_SOURCE_ALPHA,
    GLASS_RESULT_COUNT
} GlassResult;

typedef struct {
    int x, y, width, edge;
    unsigned long pixels;
} GlassPaint;

static const char *glass_reason(GlassResult result) {
    static const char *names[] = {"applied", "geometry", "target", "format",
        "transform", "clip", "bounds", "source-alpha"};
    return result < GLASS_RESULT_COUNT ? names[result] : "unknown";
}

static int glass_integer(double value) {
    return isfinite(value) && value >= -32768 && value <= 32768 && value == floor(value);
}

static unsigned glass_luminance(uint32_t pixel) {
    return (54 * ((pixel >> 16) & 255) + 183 * ((pixel >> 8) & 255) +
        19 * (pixel & 255) + 128) >> 8;
}

/* Reject before the first write. The complete current frame must be opaque,
 * freshly painted and in the dirty clip; a partially reused glass buffer must
 * never be multiplied again. Document pixels are read-only throughout. */
static GlassResult glass_compose(cairo_t *context, int width, int height, int edge,
        GlassPaint *paint) {
    *paint = (GlassPaint){0};
    if (width <= 0 || height <= 0 || width > 16384 || height > 16384 ||
            edge <= 0 || edge >= height / 2)
        return GLASS_GEOMETRY;
    cairo_surface_t *surface = cairo_get_group_target(context);
    if (cairo_status(context) != CAIRO_STATUS_SUCCESS ||
            surface != cairo_get_target(context) ||
            cairo_surface_get_type(surface) != CAIRO_SURFACE_TYPE_IMAGE ||
            cairo_surface_status(surface) != CAIRO_STATUS_SUCCESS)
        return GLASS_TARGET;
    if (cairo_image_surface_get_format(surface) != CAIRO_FORMAT_ARGB32)
        return GLASS_FORMAT;
    cairo_matrix_t matrix;
    cairo_get_matrix(context, &matrix);
    double scale_x, scale_y, offset_x, offset_y;
    cairo_surface_get_device_scale(surface, &scale_x, &scale_y);
    cairo_surface_get_device_offset(surface, &offset_x, &offset_y);
    if (matrix.xx != 1 || matrix.yy != 1 || matrix.xy != 0 || matrix.yx != 0 ||
            scale_x != 1 || scale_y != 1 || !glass_integer(matrix.x0 + offset_x) ||
            !glass_integer(matrix.y0 + offset_y))
        return GLASS_TRANSFORM;
    int x = (int)(matrix.x0 + offset_x), y = (int)(matrix.y0 + offset_y);
    if (x < 0 || y < 0 || x + width > cairo_image_surface_get_width(surface) ||
            y + height > cairo_image_surface_get_height(surface))
        return GLASS_BOUNDS;
    cairo_rectangle_list_t *clips = cairo_copy_clip_rectangle_list(context);
    cairo_region_t *region = cairo_region_create();
    int valid = clips->status == CAIRO_STATUS_SUCCESS;
    for (int i = 0; valid && i < clips->num_rectangles; i++) {
        cairo_rectangle_t rectangle = clips->rectangles[i];
        valid = glass_integer(rectangle.x) && glass_integer(rectangle.y) &&
            glass_integer(rectangle.width) && glass_integer(rectangle.height);
        if (valid) {
            cairo_rectangle_int_t box = {(int)rectangle.x, (int)rectangle.y,
                (int)rectangle.width, (int)rectangle.height};
            cairo_region_union_rectangle(region, &box);
        }
    }
    cairo_rectangle_int_t frame = {0, 0, width, height};
    valid = valid && cairo_region_contains_rectangle(region, &frame) == CAIRO_REGION_OVERLAP_IN;
    cairo_rectangle_list_destroy(clips);
    cairo_region_destroy(region);
    if (!valid)
        return GLASS_CLIP;
    cairo_surface_flush(surface);
    unsigned char *data = cairo_image_surface_get_data(surface);
    int stride = cairo_image_surface_get_stride(surface);
    if (!data || stride < (x + width) * 4)
        return GLASS_BOUNDS;
    for (int row = 0; row < height; row++) {
        const uint32_t *pixels = (const uint32_t *)(data + (y + row) * stride) + x;
        for (int column = 0; column < width; column++) {
            if ((pixels[column] >> 24) != 255)
                return GLASS_SOURCE_ALPHA;
        }
    }
    *paint = (GlassPaint){x, y, width, edge, 0};
    for (int row = 0; row < edge; row++) {
        uint32_t *pixels = (uint32_t *)(data + (y + row) * stride) + x;
        for (int column = 0; column < width; column++) {
            uint32_t pixel = pixels[column];
            unsigned r = (pixel >> 16) & 255, g = (pixel >> 8) & 255, b = pixel & 255;
            unsigned maximum = r > g ? r : g;
            maximum = maximum > b ? maximum : b;
            unsigned minimum = r < g ? r : g;
            minimum = minimum < b ? minimum : b;
            unsigned luminance = glass_luminance(pixel);
            /* Preserve color swatches/status indicators, bright foreground and
             * dark ink bordering light native input fields, including antialias. */
            int foreground = maximum - minimum >= 24 || luminance >= 174;
            for (int dy = -2; !foreground && dy <= 2; dy++) {
                if (row + dy < 0 || row + dy >= edge)
                    continue;
                const uint32_t *near = (const uint32_t *)(data + (y + row + dy) * stride) + x;
                for (int dx = -2; dx <= 2; dx++) {
                    if (column + dx >= 0 && column + dx < width &&
                            glass_luminance(near[column + dx]) >= 174) {
                        foreground = 1;
                        break;
                    }
                }
            }
            if (foreground)
                continue;
            double amount = luminance <= 77 ? 0 : (luminance - 77) / 97.0;
            amount = amount * amount * (3 - 2 * amount);
            unsigned alpha = 184 + (unsigned)(71 * amount + 0.5);
            pixels[column] = (alpha << 24) | (((r * alpha + 127) / 255) << 16) |
                (((g * alpha + 127) / 255) << 8) | ((b * alpha + 127) / 255);
            paint->pixels++;
        }
    }
    cairo_surface_mark_dirty_rectangle(surface, x, y, width, edge);
    return GLASS_APPLIED;
}
#endif
