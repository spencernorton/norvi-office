#include "header.c"
#include <gtk/gtk-a11y.h>

typedef struct { GtkWindowAccessible parent; } ClosingAccessible;
typedef struct { GtkWindowAccessibleClass parent; } ClosingAccessibleClass;
typedef struct { GtkWindow parent; } ClosingWindow;
typedef struct { GtkWindowClass parent; } ClosingWindowClass;

static gboolean close_on_states;
static guint state_hits, menu_hits, sensitivity_hits, timer_hits;
static guint focus_hits;
static gboolean close_menu_armed;

G_DEFINE_TYPE(ClosingAccessible, closing_accessible, GTK_TYPE_WINDOW_ACCESSIBLE)
G_DEFINE_TYPE(ClosingWindow, closing_window, GTK_TYPE_WINDOW)

static void close_owner(GtkWidget *window) {
    gtk_widget_destroy(window);
    /* Release ownership while the originating callback is still on-stack. */
    g_object_set_data(G_OBJECT(window), "norvi-header", NULL);
}

static AtkStateSet *closing_states(AtkObject *object) {
    if (close_on_states) {
        close_on_states = FALSE;
        state_hits++;
        GtkWidget *window = gtk_accessible_get_widget(GTK_ACCESSIBLE(object));
        g_assert_nonnull(window);
        close_owner(window);
        AtkStateSet *states = atk_state_set_new();
        atk_state_set_add_state(states, ATK_STATE_VISIBLE);
        atk_state_set_add_state(states, ATK_STATE_SHOWING);
        return states;
    }
    return ATK_OBJECT_CLASS(closing_accessible_parent_class)->ref_state_set(object);
}

static void closing_accessible_class_init(ClosingAccessibleClass *klass) {
    ATK_OBJECT_CLASS(klass)->ref_state_set = closing_states;
}
static void closing_accessible_init(ClosingAccessible *self) { (void)self; }
static void closing_window_class_init(ClosingWindowClass *klass) {
    gtk_widget_class_set_accessible_type(GTK_WIDGET_CLASS(klass), closing_accessible_get_type());
}
static void closing_window_init(ClosingWindow *self) { (void)self; }

static Header *fixture(GtkWidget **owned) {
    GtkWidget *window = g_object_ref_sink(g_object_new(closing_window_get_type(), NULL));
    gtk_window_set_default_size(GTK_WINDOW(window), 640, 480);
    Header *header = g_new0(Header, 1);
    header->refs = 1;
    header->identity = g_uuid_string_random();
    header->window = window;
    header->cancel = g_cancellable_new();
    header->bar = gtk_header_bar_new();
    gtk_window_set_titlebar(GTK_WINDOW(window), header->bar);
    header->menu = gtk_menu_button_new();
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header->bar), header->menu);
    for (guint i = 0; i < G_N_ELEMENTS(header->buttons); i++) {
        header->buttons[i] = gtk_button_new();
        gtk_header_bar_pack_start(GTK_HEADER_BAR(header->bar), header->buttons[i]);
    }
    g_object_set_data_full(G_OBJECT(window), "norvi-header", header, header_unref);
    connect_header(window, "destroy", G_CALLBACK(destroyed), header, 0);
    gtk_widget_show_all(window);
    gtk_widget_realize(window);
    *owned = window;
    return header;
}

static void report_destroyed_during_atk(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    guint before = state_hits;
    close_on_states = TRUE;
    /* The production function measures before its Wayland transport gate.
     * Xvfb must enter ref_state_set, not silently return at window_handle(). */
    g_assert_false(report_native_geometry(header, NULL));
    g_assert_cmpuint(state_hits, ==, before + 1);
    g_assert_null(g_object_get_data(G_OBJECT(window), "norvi-header"));
    g_object_unref(window);
}

static gboolean refresh_from_timer(gpointer data) {
    timer_hits++;
    close_on_states = TRUE;
    return refresh(data);
}

static void timer_destroyed_during_atk(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    guint before = state_hits;
    guint timers_before = timer_hits;
    header->timer = g_timeout_add_full(G_PRIORITY_DEFAULT, 1, refresh_from_timer, header_ref(header), header_unref);
    guint timer = header->timer;
    close_on_states = FALSE;
    gint64 deadline = g_get_monotonic_time() + G_TIME_SPAN_SECOND;
    while (state_hits == before && g_get_monotonic_time() < deadline)
        g_main_context_iteration(NULL, FALSE);
    g_assert_cmpuint(state_hits, ==, before + 1);
    g_assert_cmpuint(timer_hits, ==, timers_before + 1);
    g_assert_null(g_main_context_find_source_by_id(NULL, timer));
    g_assert_null(g_object_get_data(G_OBJECT(window), "norvi-header"));
    g_object_unref(window);
}

static void close_during_menu(GObject *object, GParamSpec *property, gpointer data) {
    (void)object;
    (void)property;
    if (close_menu_armed) {
        close_menu_armed = FALSE;
        menu_hits++;
        close_owner(data);
    }
}

static void menu_install_destroys_window(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    GMenu *model = g_menu_new();
    g_menu_append(model, "Fixture", "win.fixture");
    GSimpleActionGroup *actions = g_simple_action_group_new();
    GSimpleAction *action = g_simple_action_new("fixture", NULL);
    g_action_map_add_action(G_ACTION_MAP(actions), G_ACTION(action));
    g_object_unref(action);
    GdkWindow *surface = gtk_widget_get_window(window);
    g_object_set_data_full(G_OBJECT(surface), "g-lo-menubar", model, g_object_unref);
    g_object_set_data_full(G_OBJECT(surface), "g-lo-action-group", actions, g_object_unref);
    guint before = menu_hits;
    close_menu_armed = TRUE;
    g_signal_connect(header->menu, "notify::menu-model", G_CALLBACK(close_during_menu), window);
    g_assert_false(refresh(header));
    g_assert_cmpuint(menu_hits, >=, before + 1);
    g_assert_null(g_object_get_data(G_OBJECT(window), "norvi-header"));
    g_object_unref(window);
}

static void close_when_enabled(GObject *object, GParamSpec *property, gpointer data) {
    (void)property;
    if (gtk_widget_get_sensitive(GTK_WIDGET(object))) {
        sensitivity_hits++;
        close_owner(data);
    }
}

static void async_description_destroys_window(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    guint before = sensitivity_hits;
    g_signal_connect(header->buttons[0], "notify::sensitive", G_CALLBACK(close_when_enabled), window);
    GVariantBuilder builder;
    g_variant_builder_init(&builder, G_VARIANT_TYPE("a{sb}"));
    for (guint i = 0; i < G_N_ELEMENTS(commands); i++)
        g_variant_builder_add(&builder, "{sb}", commands[i], TRUE);
    GVariant *states = g_variant_ref_sink(g_variant_builder_end(&builder));
    apply_description(header, states);
    g_variant_unref(states);
    g_assert_cmpuint(sensitivity_hits, ==, before + 1);
    g_assert_null(g_object_get_data(G_OBJECT(window), "norvi-header"));
    g_object_unref(window);
}

static void close_during_focus(GObject *object, GParamSpec *property, gpointer data) {
    (void)object;
    (void)property;
    focus_hits++;
    close_owner(data);
}

static void focus_handoff_destroys_window(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    GtkWidget *client = gtk_fixed_new();
    gtk_container_add(GTK_CONTAINER(window), client);
    gtk_widget_show(client);
    gtk_window_set_focus(GTK_WINDOW(window), header->buttons[0]);
    g_signal_connect(client, "notify::can-focus", G_CALLBACK(close_during_focus), window);
    guint before = focus_hits;
    GdkEventKey event = {.keyval = GDK_KEY_F6};
    g_assert_true(header_key(window, &event, header));
    g_assert_cmpuint(focus_hits, ==, before + 1);
    g_assert_null(g_object_get_data(G_OBJECT(window), "norvi-header"));
    g_object_unref(window);
}

int main(int argc, char **argv) {
    g_test_init(&argc, &argv, NULL);
    /* Missing display is a failed native check, never a successful skip. */
    g_assert_true(gtk_init_check(&argc, &argv));
    g_log_set_always_fatal(G_LOG_FATAL_MASK | G_LOG_LEVEL_CRITICAL);
    native_desktop = TRUE;
    g_test_add_func("/native-header/lifecycle/report-atk-destroy", report_destroyed_during_atk);
    g_test_add_func("/native-header/lifecycle/timer-atk-destroy", timer_destroyed_during_atk);
    g_test_add_func("/native-header/lifecycle/menu-install-destroy", menu_install_destroys_window);
    g_test_add_func("/native-header/lifecycle/async-description-destroy", async_description_destroys_window);
    g_test_add_func("/native-header/lifecycle/focus-handoff-destroy", focus_handoff_destroys_window);
    return g_test_run();
}
