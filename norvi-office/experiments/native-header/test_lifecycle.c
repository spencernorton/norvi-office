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
static gboolean destroy_pumps_context;
static guint destroy_pump_hits;

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

static void pump_before_destroy(GtkWidget *widget, gpointer data) {
    (void)widget;
    (void)data;
    if (!destroy_pumps_context)
        return;
    destroy_pumps_context = FALSE;
    destroy_pump_hits++;
    for (guint i = 0; i < 64 && g_main_context_iteration(NULL, FALSE); i++) {}
}

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
    header->menu = header_menu_new();
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header->bar), header->menu);
    for (guint i = 0; i < G_N_ELEMENTS(header->buttons); i++) {
        header->buttons[i] = gtk_button_new();
        gtk_header_bar_pack_start(GTK_HEADER_BAR(header->bar), header->buttons[i]);
    }
    g_object_set_data_full(G_OBJECT(window), "norvi-header", header, header_unref);
    g_signal_connect(window, "destroy", G_CALLBACK(pump_before_destroy), NULL);
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
    start_header_timer(header, 1, refresh_from_timer);
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

static gboolean refresh_counted(gpointer data) {
    timer_hits++;
    return refresh(data);
}

static void earlier_destroy_handler_removes_timer(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    guint before = timer_hits, pumps_before = destroy_pump_hits;
    start_header_timer(header, 0, refresh_counted);
    guint timer = header->timer;
    destroy_pumps_context = TRUE;
    gtk_widget_destroy(window);
    g_assert_cmpuint(destroy_pump_hits, ==, pumps_before + 1);
    g_assert_cmpuint(timer_hits, ==, before + 1);
    g_assert_cmpuint(header->timer, ==, 0);
    g_assert_null(g_main_context_find_source_by_id(NULL, timer));
    g_object_set_data(G_OBJECT(window), "norvi-header", NULL);
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

static GtkWidget *fixture_popup(Header *header) {
    GtkWidget *popup = g_object_ref_sink(gtk_menu_new());
    gtk_menu_shell_append(GTK_MENU_SHELL(popup), gtk_menu_item_new_with_label("Fixture item"));
    gtk_widget_show_all(popup);
    gtk_widget_hide(popup);
    gtk_menu_button_set_popup(GTK_MENU_BUTTON(header->menu), popup);
    gtk_widget_set_sensitive(header->menu, TRUE);
    return popup;
}

static void programmatic_menu_toggle_closes_popup(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    GtkWidget *popup = fixture_popup(header);
    g_assert_true(header_menu_anchor_live((NorviHeaderMenuButton *)header->menu));
    /* GTK documents a nullable trigger event but warns for ATK/programmatic
     * activation without one. That warning is not an invalid anchor. GTK logs
     * it as a structured message, which g_test_expect_message() cannot see,
     * so it is left to print. */
    gtk_button_clicked(GTK_BUTTON(header->menu));
    g_assert_true(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(header->menu)));
    g_assert_true(gtk_widget_get_visible(popup));
    gtk_button_clicked(GTK_BUTTON(header->menu));
    g_assert_false(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(header->menu)));
    g_assert_false(gtk_widget_get_visible(popup));
    close_owner(window);
    g_object_unref(popup);
    g_object_unref(window);
}

static guint queued_menu_hits, state_close_hits, anchor_close_hits;
static gboolean state_close_armed, anchor_close_armed;

static gboolean queued_menu_click(gpointer data) {
    GtkWidget *button = data;
    GtkWidget *top = gtk_widget_get_toplevel(button);
    queued_menu_hits++;
    g_assert_true(GTK_IS_WINDOW(top));
    g_assert_true(gtk_widget_in_destruction(top));
    g_assert_false(gtk_widget_get_realized(top));
    /* Catch the actual dangerous interval before the child is disposed and
     * clears its popup. A fully disposed button would be a false-pass fixture. */
    g_assert_nonnull(gtk_menu_button_get_popup(GTK_MENU_BUTTON(button)));
    gtk_button_clicked(GTK_BUTTON(button));
    g_assert_false(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(button)));
    return G_SOURCE_REMOVE;
}

static void queued_menu_click_during_owner_teardown(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    GtkWidget *popup = fixture_popup(header);
    guint before = queued_menu_hits, pumps_before = destroy_pump_hits;
    g_idle_add_full(G_PRIORITY_DEFAULT, queued_menu_click, g_object_ref(header->menu), g_object_unref);
    destroy_pumps_context = TRUE;
    close_owner(window);
    g_assert_cmpuint(queued_menu_hits, ==, before + 1);
    g_assert_cmpuint(destroy_pump_hits, ==, pumps_before + 1);
    g_assert_false(gtk_widget_get_visible(popup));
    g_object_unref(popup);
    g_object_unref(window);
}

static void close_on_checked(GtkWidget *button, GtkStateFlags previous, gpointer data) {
    (void)previous;
    if (state_close_armed && (gtk_widget_get_state_flags(button) & GTK_STATE_FLAG_CHECKED)) {
        state_close_armed = FALSE;
        state_close_hits++;
        close_owner(data);
    }
}

static void menu_toggle_state_closes_owner(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    GtkWidget *popup = fixture_popup(header);
    GtkWidget *button = g_object_ref(header->menu);
    guint before = state_close_hits;
    state_close_armed = TRUE;
    g_signal_connect(button, "state-flags-changed", G_CALLBACK(close_on_checked), window);
    gtk_button_clicked(GTK_BUTTON(button));
    g_assert_cmpuint(state_close_hits, ==, before + 1);
    g_assert_false(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(button)));
    g_assert_false(gtk_widget_get_visible(popup));
    g_object_unref(button);
    g_object_unref(popup);
    g_object_unref(window);
}

static void close_on_anchor(GObject *object, GParamSpec *property, gpointer data) {
    (void)object;
    (void)property;
    if (anchor_close_armed) {
        anchor_close_armed = FALSE;
        anchor_close_hits++;
        close_owner(data);
    }
}

static void menu_anchor_notification_closes_owner(void) {
    GtkWidget *window;
    Header *header = fixture(&window);
    GtkWidget *popup = fixture_popup(header);
    GtkWidget *button = g_object_ref(header->menu);
    guint before = anchor_close_hits;
    anchor_close_armed = TRUE;
    g_signal_connect(popup, "notify::anchor-hints", G_CALLBACK(close_on_anchor), window);
    gtk_button_clicked(GTK_BUTTON(button));
    g_assert_cmpuint(anchor_close_hits, ==, before + 1);
    g_assert_false(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(button)));
    g_assert_false(gtk_widget_get_visible(popup));
    g_object_unref(button);
    g_object_unref(popup);
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
    g_test_add_func("/native-header/lifecycle/earlier-destroy-handler", earlier_destroy_handler_removes_timer);
    g_test_add_func("/native-header/lifecycle/menu-install-destroy", menu_install_destroys_window);
    g_test_add_func("/native-header/lifecycle/async-description-destroy", async_description_destroys_window);
    g_test_add_func("/native-header/lifecycle/focus-handoff-destroy", focus_handoff_destroys_window);
    g_test_add_func("/native-header/lifecycle/programmatic-menu-toggle", programmatic_menu_toggle_closes_popup);
    g_test_add_func("/native-header/lifecycle/queued-menu-click-teardown", queued_menu_click_during_owner_teardown);
    g_test_add_func("/native-header/lifecycle/menu-toggle-state-destroy", menu_toggle_state_closes_owner);
    g_test_add_func("/native-header/lifecycle/menu-anchor-notify-destroy", menu_anchor_notification_closes_owner);
    return g_test_run();
}
