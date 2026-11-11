/* Launch-scoped GTK3 header for the isolated Norvi Office preview.
 * Public GTK APIs only; no LibreOffice binary or system files are patched. */
#include <gtk/gtk.h>
#include <gmodule.h>
#include <gdk/gdkwayland.h>
#include <unistd.h>

typedef struct {
    gint refs;
    GtkWidget *window, *bar, *menu, *buttons[5];
    GDBusConnection *bus;
    GCancellable *cancel;
    GMenuModel *model;
    GActionGroup *actions;
    guint timer;
    gboolean destroyed, describing, activating;
    gchar *identity, *menu_signature;
} Header;

static const char *commands[] = {"open", "save", "undo", "redo", "settings"};
static const char *labels[] = {"Open", "Save", "Undo", "Redo", "Settings"};
static const char *icons[] = {"document-open-symbolic", "document-save-symbolic",
    "edit-undo-symbolic", "edit-redo-symbolic", "emblem-system-symbolic"};
static const char *study_paths[] = {
    "M2 7V4h7l3 3h10v3M2 7h20l-3 12H2Z",
    "M4 3h13l4 4v14H3V3h1m3 0v7h10V3M7 21v-7h10v7",
    "m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12",
    "m16 4 5 5-5 5m5-5H10a6 6 0 0 0 0 12",
};

static GtkWidget *study_icon(guint index) {
    gchar *svg = g_strdup_printf(
        "<svg xmlns='http://www.w3.org/2000/svg' width='17' height='17' viewBox='0 0 24 24'>"
        "<path d='%s' fill='none' stroke='#f2eff8' stroke-width='1.55' "
        "stroke-linecap='round' stroke-linejoin='round'/></svg>", study_paths[index]);
    GdkPixbufLoader *loader = gdk_pixbuf_loader_new();
    gboolean written = gdk_pixbuf_loader_write(loader, (const guchar *)svg, strlen(svg), NULL);
    gboolean closed = gdk_pixbuf_loader_close(loader, NULL);
    GdkPixbuf *pixbuf = written && closed ? gdk_pixbuf_loader_get_pixbuf(loader) : NULL;
    GtkWidget *image = pixbuf ? gtk_image_new_from_pixbuf(pixbuf) : NULL;
    g_object_unref(loader);
    g_free(svg);
    return image;
}

static GSettings *popup_settings, *interface_settings, *contrast_settings;
static const char *token;

static Header *header_ref(Header *header) {
    g_atomic_int_inc(&header->refs);
    return header;
}

static void header_unref(gpointer data) {
    Header *header = data;
    if (!g_atomic_int_dec_and_test(&header->refs))
        return;
    g_clear_object(&header->bus);
    g_clear_object(&header->cancel);
    g_clear_object(&header->model);
    g_clear_object(&header->actions);
    g_free(header->identity);
    g_free(header->menu_signature);
    g_free(header);
}

static void destroyed(GtkWidget *widget, gpointer data) {
    (void)widget;
    Header *header = data;
    header->destroyed = TRUE;
    header->window = NULL;
    if (header->timer) {
        g_source_remove(header->timer);
        header->timer = 0;
    }
    g_cancellable_cancel(header->cancel);
}

static void disable_actions(Header *header) {
    for (guint i = 0; i < G_N_ELEMENTS(commands); i++)
        gtk_widget_set_sensitive(header->buttons[i], FALSE);
}

typedef struct { Header *header; } Request;

static guint64 window_handle(Header *header) {
    if (header->destroyed || !gtk_widget_get_realized(header->window))
        return 0;
    GdkWindow *surface = gtk_widget_get_window(header->window);
    if (!GDK_IS_WAYLAND_DISPLAY(gdk_window_get_display(surface)))
        return 0;
    return (guint64)(guintptr)gdk_wayland_window_get_wl_surface(surface);
}

static Request *request_new(Header *header) {
    Request *request = g_new0(Request, 1);
    request->header = header_ref(header);
    return request;
}

static void request_free(Request *request) {
    header_unref(request->header);
    g_free(request);
}

static void described(GObject *source, GAsyncResult *result, gpointer data) {
    Request *request = data;
    Header *header = request->header;
    GError *error = NULL;
    GVariant *reply = g_dbus_connection_call_finish(G_DBUS_CONNECTION(source), result, &error);
    header->describing = FALSE;
    if (!header->destroyed && !header->activating) {
        disable_actions(header);
        if (reply) {
            GVariant *states = g_variant_get_child_value(reply, 0);
            for (guint i = 0; i < G_N_ELEMENTS(commands); i++) {
                gboolean enabled = FALSE;
                g_variant_lookup(states, commands[i], "b", &enabled);
                gtk_widget_set_sensitive(header->buttons[i], enabled);
            }
            g_variant_unref(states);
        }
    }
    g_clear_pointer(&reply, g_variant_unref);
    g_clear_error(&error);
    request_free(request);
}

static void activated(GObject *source, GAsyncResult *result, gpointer data) {
    Request *request = data;
    GError *error = NULL;
    GVariant *reply = g_dbus_connection_call_finish(G_DBUS_CONNECTION(source), result, &error);
    request->header->activating = FALSE;
    g_clear_pointer(&reply, g_variant_unref);
    g_clear_error(&error);
    request_free(request);
}

static void clicked(GtkButton *button, gpointer data) {
    Header *header = data;
    if (header->destroyed || header->activating || !header->bus)
        return;
    const char *command = g_object_get_data(G_OBJECT(button), "norvi-command");
    Request *request = request_new(header);
    header->activating = TRUE;
    disable_actions(header);
    g_dbus_connection_call(header->bus, "dev.norvi.OfficeHeader", "/dev/norvi/OfficeHeader",
        "dev.norvi.OfficeHeader", "Activate",
        g_variant_new("(utsss)", (guint)getpid(), window_handle(header), header->identity, command, token),
        G_VARIANT_TYPE("(b)"), G_DBUS_CALL_FLAGS_NO_AUTO_START, 30000,
        header->cancel, activated, request);
}

static GtkWidget *document_focus(GtkWidget *widget) {
    if (GTK_IS_FIXED(widget))
        return widget;
    if (!GTK_IS_CONTAINER(widget))
        return NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(widget));
    GtkWidget *found = NULL;
    for (GList *node = children; node && !found; node = node->next)
        found = document_focus(node->data);
    g_list_free(children);
    return found;
}

static gboolean header_key(GtkWidget *window, GdkEventKey *event, gpointer data) {
    Header *header = data;
    guint modifiers = event->state & gtk_accelerator_get_default_mod_mask();
    if (event->keyval == GDK_KEY_F10 && modifiers == 0 && gtk_widget_get_sensitive(header->menu)) {
        gtk_widget_grab_focus(header->menu);
        gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(header->menu), TRUE);
        return TRUE;
    }
    GtkWidget *focus = gtk_window_get_focus(GTK_WINDOW(window));
    if (focus && gtk_widget_is_ancestor(focus, header->bar) && modifiers == 0 &&
            (event->keyval == GDK_KEY_Escape || event->keyval == GDK_KEY_F6)) {
        GtkWidget *client = document_focus(gtk_bin_get_child(GTK_BIN(window)));
        if (client) {
            gtk_widget_set_can_focus(client, TRUE);
            gtk_widget_grab_focus(client);
            return TRUE;
        }
    }
    return FALSE;
}

static gboolean blurred_menu(void) {
    gchar *theme = NULL;
    gboolean prefer_dark = FALSE;
    g_object_get(gtk_settings_get_default(), "gtk-theme-name", &theme,
        "gtk-application-prefer-dark-theme", &prefer_dark, NULL);
    gchar *lower = g_ascii_strdown(theme ? theme : "", -1);
    const char *forced = g_getenv("GTK_THEME");
    gboolean contrast = strstr(lower, "highcontrast") != NULL ||
        (forced && g_strrstr(forced, "HighContrast")) ||
        g_settings_get_boolean(contrast_settings, "high-contrast");
    gchar *scheme = g_settings_get_string(interface_settings, "color-scheme");
    gboolean dark = prefer_dark || strstr(lower, "dark") ||
        (forced && strstr(forced, "dark")) || g_strcmp0(scheme, "prefer-dark") == 0;
    gboolean blur = popup_settings && g_settings_get_boolean(popup_settings, "blur");
    g_free(theme);
    g_free(lower);
    g_free(scheme);
    return blur && dark && !contrast;
}

static void style_menu(GtkWidget *menu) {
    GtkStyleContext *style = gtk_widget_get_style_context(menu);
    gtk_style_context_add_class(style, "norvi-header-menu");
    if (blurred_menu())
        gtk_style_context_add_class(style, "norvi-blurred-menu");
    else
        gtk_style_context_remove_class(style, "norvi-blurred-menu");
    GtkWidget *top = gtk_widget_get_toplevel(menu);
    if (GTK_IS_WINDOW(top))
        gtk_style_context_add_class(gtk_widget_get_style_context(top), "norvi-header-popup");
    GList *children = gtk_container_get_children(GTK_CONTAINER(menu));
    for (GList *node = children; node; node = node->next) {
        if (GTK_IS_MENU_ITEM(node->data)) {
            GtkWidget *sub = gtk_menu_item_get_submenu(GTK_MENU_ITEM(node->data));
            if (sub)
                style_menu(sub);
        }
    }
    g_list_free(children);
}

static void append_menus(GMenuModel *source, GMenu *target, GHashTable *seen,
        GString *signature, guint depth) {
    if (depth > 4)
        return;
    for (gint i = 0; i < g_menu_model_get_n_items(source); i++) {
        GMenuModel *section = g_menu_model_get_item_link(source, i, G_MENU_LINK_SECTION);
        if (section) {
            append_menus(section, target, seen, signature, depth + 1);
            g_object_unref(section);
            continue;
        }
        gchar *action = NULL, *label = NULL;
        g_menu_model_get_item_attribute(source, i, "submenu-action", "s", &action);
        if (!action)
            g_menu_model_get_item_attribute(source, i, G_MENU_ATTRIBUTE_ACTION, "s", &action);
        g_menu_model_get_item_attribute(source, i, G_MENU_ATTRIBUTE_LABEL, "s", &label);
        if (action && !g_hash_table_contains(seen, action)) {
            g_hash_table_add(seen, g_strdup(action));
            GMenuItem *item = g_menu_item_new_from_model(source, i);
            g_menu_append_item(target, item);
            g_object_unref(item);
            g_string_append_printf(signature, "%s:%s;", action, label ? label : "");
        }
        g_free(action);
        g_free(label);
    }
}

static gboolean refresh(gpointer data) {
    Header *header = data;
    if (header->destroyed)
        return G_SOURCE_REMOVE;
    if (!gtk_widget_get_realized(header->window))
        return G_SOURCE_CONTINUE;
    GdkWindow *surface = gtk_widget_get_window(header->window);
    /* Read the pinned GTK backend's exported menu, never its private structs. */
    GMenuModel *model = g_object_get_data(G_OBJECT(surface), "g-lo-menubar");
    GActionGroup *actions = g_object_get_data(G_OBJECT(surface), "g-lo-action-group");
    if (G_IS_MENU_MODEL(model) && G_IS_ACTION_GROUP(actions) &&
            g_menu_model_get_n_items(model) > 0) {
        GMenu *flat = g_menu_new();
        GHashTable *seen = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
        GString *signature = g_string_new(NULL);
        append_menus(model, flat, seen, signature, 0);
        if (g_menu_model_get_n_items(G_MENU_MODEL(flat)) &&
                g_strcmp0(signature->str, header->menu_signature) != 0 &&
                !gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(header->menu))) {
            g_free(header->menu_signature);
            header->menu_signature = g_strdup(signature->str);
            g_set_object(&header->model, model);
            g_set_object(&header->actions, actions);
            gtk_widget_insert_action_group(header->menu, "win", actions);
            gtk_menu_button_set_menu_model(GTK_MENU_BUTTON(header->menu), G_MENU_MODEL(flat));
            gtk_widget_set_sensitive(header->menu, TRUE);
        }
        g_string_free(signature, TRUE);
        g_hash_table_unref(seen);
        g_object_unref(flat);
    }
    GtkWidget *popup = GTK_WIDGET(gtk_menu_button_get_popup(GTK_MENU_BUTTON(header->menu)));
    if (popup)
        style_menu(popup);
    if (!header->bus || header->describing || header->activating)
        return G_SOURCE_CONTINUE;
    if (!window_handle(header))
        return G_SOURCE_CONTINUE;
    header->describing = TRUE;
    Request *request = request_new(header);
    g_dbus_connection_call(header->bus, "dev.norvi.OfficeHeader", "/dev/norvi/OfficeHeader",
        "dev.norvi.OfficeHeader", "Describe",
        g_variant_new("(utss)", (guint)getpid(), window_handle(header), header->identity, token),
        G_VARIANT_TYPE("(a{sb})"),
        G_DBUS_CALL_FLAGS_NO_AUTO_START, 1000, header->cancel, described, request);
    return G_SOURCE_CONTINUE;
}

static gboolean calc_caption(GBinding *binding, const GValue *source,
        GValue *target, gpointer data) {
    (void)binding;
    (void)data;
    const gchar *title = g_value_get_string(source);
    const gchar *suffix = " — LibreOffice Calc";
    if (title && g_str_has_suffix(title, suffix)) {
        gchar *escaped = g_markup_escape_text(title, strlen(title) - strlen(suffix));
        g_value_take_string(target, g_strdup_printf("%s <span weight='normal' alpha='75%%'>· Calc</span>",
            escaped));
        g_free(escaped);
    } else {
        g_value_take_string(target, g_markup_escape_text(title ? title : "", -1));
    }
    return TRUE;
}

static gboolean child_added(GSignalInvocationHint *hint, guint count,
        const GValue *values, gpointer data) {
    (void)hint;
    (void)data;
    if (count < 2)
        return TRUE;
    GtkWidget *window = g_value_get_object(values);
    GtkWidget *child = g_value_get_object(values + 1);
    if (!GTK_IS_WINDOW(window) || GTK_IS_DIALOG(window) || !GTK_IS_GRID(child) ||
            gtk_widget_get_realized(window) ||
            gtk_window_get_window_type(GTK_WINDOW(window)) != GTK_WINDOW_TOPLEVEL ||
            gtk_window_get_type_hint(GTK_WINDOW(window)) != GDK_WINDOW_TYPE_HINT_NORMAL ||
            gtk_window_get_transient_for(GTK_WINDOW(window)) ||
            g_object_get_data(G_OBJECT(window), "norvi-header"))
        return TRUE;
    if (g_strcmp0(g_object_get_data(G_OBJECT(window), "libo-version"), "26.2.6.3") != 0)
        return TRUE;

    Header *header = g_new0(Header, 1);
    header->refs = 1;
    header->identity = g_uuid_string_random();
    header->window = window;
    header->cancel = g_cancellable_new();
    header->bus = g_bus_get_sync(G_BUS_TYPE_SESSION, NULL, NULL);
    g_object_set_data_full(G_OBJECT(window), "norvi-header", header, header_unref);
    g_signal_connect(window, "destroy", G_CALLBACK(destroyed), header);
    header->bar = gtk_window_get_titlebar(GTK_WINDOW(window));
    if (!GTK_IS_HEADER_BAR(header->bar)) {
        header->bar = gtk_header_bar_new();
        gtk_window_set_titlebar(GTK_WINDOW(window), header->bar);
    }
    gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header->bar), TRUE);
    gtk_header_bar_set_has_subtitle(GTK_HEADER_BAR(header->bar), FALSE);
    atk_object_set_name(gtk_widget_get_accessible(header->bar), "Document controls");
    gtk_style_context_add_class(gtk_widget_get_style_context(header->bar), "norvi-office-header");
    GtkWidget *title = gtk_label_new(NULL);
    gtk_label_set_ellipsize(GTK_LABEL(title), PANGO_ELLIPSIZE_END);
    gtk_label_set_max_width_chars(GTK_LABEL(title), 46);
    gtk_style_context_add_class(gtk_widget_get_style_context(title), "title");
    if (g_strcmp0(g_getenv("NORVI_OFFICE_CALC_RIBBON"), "1") == 0) {
        gtk_label_set_use_markup(GTK_LABEL(title), TRUE);
        g_object_bind_property_full(window, "title", title, "label", G_BINDING_SYNC_CREATE,
            calc_caption, NULL, NULL, NULL);
    } else {
        g_object_bind_property(window, "title", title, "label", G_BINDING_SYNC_CREATE);
    }
    gtk_header_bar_set_custom_title(GTK_HEADER_BAR(header->bar), title);
    const gchar *theme = g_getenv("GTK_THEME");
    gboolean study = g_strcmp0(g_getenv("NORVI_OFFICE_CALC_RIBBON"), "1") == 0 &&
        theme && strstr(theme, "dark");
    for (guint i = 0; i < G_N_ELEMENTS(commands); i++) {
        GtkWidget *button = gtk_button_new_from_icon_name(icons[i], GTK_ICON_SIZE_BUTTON);
        GtkWidget *image = study && i < G_N_ELEMENTS(study_paths) ? study_icon(i) : NULL;
        if (image)
            gtk_button_set_image(GTK_BUTTON(button), image);
        header->buttons[i] = button;
        gtk_widget_set_focus_on_click(button, FALSE);
        gtk_widget_set_tooltip_text(button, labels[i]);
        atk_object_set_name(gtk_widget_get_accessible(button), labels[i]);
        gtk_style_context_add_class(gtk_widget_get_style_context(button), "flat");
        g_object_set_data(G_OBJECT(button), "norvi-command", (gpointer)commands[i]);
        g_signal_connect(button, "clicked", G_CALLBACK(clicked), header);
        if (i == 4)
            gtk_header_bar_pack_end(GTK_HEADER_BAR(header->bar), button);
        else
            gtk_header_bar_pack_start(GTK_HEADER_BAR(header->bar), button);
    }
    disable_actions(header);
    header->menu = gtk_menu_button_new();
    gtk_menu_button_set_use_popover(GTK_MENU_BUTTON(header->menu), FALSE);
    gtk_button_set_image(GTK_BUTTON(header->menu),
        gtk_image_new_from_icon_name("open-menu-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_style_context_add_class(gtk_widget_get_style_context(header->menu), "flat");
    gtk_widget_set_tooltip_text(header->menu, "Main menu");
    atk_object_set_name(gtk_widget_get_accessible(header->menu), "Main menu");
    gtk_widget_set_sensitive(header->menu, FALSE);
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header->bar), header->menu);
    g_signal_connect(window, "key-press-event", G_CALLBACK(header_key), header);
    gtk_widget_show_all(header->bar);
    header->timer = g_timeout_add(350, refresh, header);
    return TRUE;
}

/* Suspend the compositor mask before GTK forwards chrome input to VCL.
 * Root coordinates are not needed on Wayland: translate the event surface
 * back to the native GtkWindow. The compositor decides whether y is chrome. */
static void prepare_chrome(GDBusConnection *bus, gint y) {
    if (!bus)
        return;
    GVariant *reply = g_dbus_connection_call_sync(bus, "org.gnome.Shell",
        "/dev/norvi/OfficeGeometry", "dev.norvi.OfficeGeometry", "PrepareChrome",
        g_variant_new("(i)", y), G_VARIANT_TYPE("()"), G_DBUS_CALL_FLAGS_NO_AUTO_START,
        120, NULL, NULL);
    g_clear_pointer(&reply, g_variant_unref);
}

static gboolean chrome_input(GSignalInvocationHint *hint, guint count,
        const GValue *values, gpointer data) {
    (void)hint;
    (void)data;
    if (count < 2)
        return TRUE;
    GdkEvent *event = g_value_get_boxed(values + 1);
    if (!event || (event->type != GDK_BUTTON_PRESS && event->type != GDK_BUTTON_RELEASE))
        return TRUE;
    GtkWidget *widget = g_value_get_object(values);
    GtkWidget *window = gtk_widget_get_toplevel(widget);
    Header *header = g_object_get_data(G_OBJECT(window), "norvi-header");
    if (!header || header->destroyed)
        return TRUE;
    GdkWindow *surface = gdk_event_get_window(event);
    GdkWindow *top = gtk_widget_get_window(window);
    gdouble x, y;
    if (!top || !gdk_event_get_coords(event, &x, &y))
        return TRUE;
    while (surface && surface != top) {
        gdk_window_coords_to_parent(surface, x, y, &x, &y);
        surface = gdk_window_get_parent(surface);
    }
    if (surface == top && y >= 0 && y < 360)
        prepare_chrome(header->bus, (gint)y);
    return TRUE;
}

static gboolean menu_activation(GSignalInvocationHint *hint, guint count,
        const GValue *values, gpointer data) {
    (void)hint;
    (void)count;
    (void)values;
    (void)data;
    GList *windows = gtk_window_list_toplevels();
    for (GList *item = windows; item; item = item->next) {
        Header *header = g_object_get_data(G_OBJECT(item->data), "norvi-header");
        if (header && !header->destroyed && gtk_widget_get_mapped(header->window)) {
            prepare_chrome(header->bus, -1);
            break;
        }
    }
    g_list_free(windows);
    return TRUE;
}

G_MODULE_EXPORT void gtk_module_init(gint *argc, gchar ***argv) {
    (void)argc;
    (void)argv;
    const char *root = g_getenv("NORVI_OFFICE_TEST_DIR");
    token = g_getenv("NORVI_OFFICE_HEADER_TOKEN");
    if (!root || !token || strlen(token) < 32)
        return;
    gchar *config = g_build_filename(root, "config", NULL);
    gboolean isolated = g_strcmp0(config, g_getenv("XDG_CONFIG_HOME")) == 0;
    g_free(config);
    if (!isolated)
        return;
    interface_settings = g_settings_new("org.gnome.desktop.interface");
    contrast_settings = g_settings_new("org.gnome.desktop.a11y.interface");
    const char *schemas = g_getenv("NORVI_OFFICE_POPUP_SCHEMAS");
    if (schemas) {
        GSettingsSchemaSource *source = g_settings_schema_source_new_from_directory(schemas,
            g_settings_schema_source_get_default(), FALSE, NULL);
        if (source) {
            GSettingsSchema *schema = g_settings_schema_source_lookup(source,
                "org.gnome.shell.extensions.blur-my-shell.popup", FALSE);
            if (schema) {
                popup_settings = g_settings_new_full(schema, NULL, NULL);
                g_settings_schema_unref(schema);
            }
            g_settings_schema_source_unref(source);
        }
    }
    GtkCssProvider *css = gtk_css_provider_new();
    gtk_css_provider_load_from_data(css,
        "headerbar.norvi-office-header { background-image: none; background-color: @theme_bg_color;"
        " box-shadow: none; border: 0; margin: 0; }"
        ".norvi-header-menu { background-image: none; background-color: @theme_bg_color;"
        " color: @theme_fg_color; border-radius: 20px; padding: 6px; }"
        ".norvi-office-header button.flat, .norvi-header-menu menuitem {"
        " transition: background-color 110ms ease-out; }"
        ".norvi-office-header button.flat:hover, .norvi-header-menu menuitem:hover {"
        " background-color: alpha(@theme_fg_color, 0.11); }"
        ".norvi-header-menu menuitem { border-radius: 8px; padding: 6px 10px; }"
        ".norvi-header-menu.norvi-blurred-menu { background-color: rgba(45,45,50,0.88); color: white; }"
        "window.norvi-header-popup, window.norvi-header-popup.background { background-color: transparent; }",
        -1, NULL);
    gtk_style_context_add_provider_for_screen(gdk_screen_get_default(), GTK_STYLE_PROVIDER(css),
        GTK_STYLE_PROVIDER_PRIORITY_USER + 1);
    g_object_unref(css);
    g_type_class_ref(GTK_TYPE_WIDGET);
    g_type_class_ref(GTK_TYPE_MENU_ITEM);
    g_signal_add_emission_hook(g_signal_lookup("event", GTK_TYPE_WIDGET), 0, chrome_input, NULL, NULL);
    g_signal_add_emission_hook(g_signal_lookup("activate", GTK_TYPE_MENU_ITEM), 0, menu_activation, NULL, NULL);
    g_type_class_ref(GTK_TYPE_CONTAINER);
    g_signal_add_emission_hook(g_signal_lookup("add", GTK_TYPE_CONTAINER), 0, child_added, NULL, NULL);
}
