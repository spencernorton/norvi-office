#include "header.c"

static GMenu *section_with_item(const char *label, const char *identity) {
    GMenu *section = g_menu_new();
    GMenu *submenu = g_menu_new();
    g_menu_append(submenu, "Save", "win.save");
    GMenuItem *item = g_menu_item_new_submenu(label, G_MENU_MODEL(submenu));
    g_menu_item_set_attribute(item, "submenu-action", "s", identity);
    g_menu_append_item(section, item);
    g_object_unref(item);
    g_object_unref(submenu);
    return section;
}

static void verify_count(GMenu *root, gint expected) {
    GMenu *flat = g_menu_new();
    GHashTable *seen = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    GString *signature = g_string_new(NULL);
    append_menus(G_MENU_MODEL(root), flat, seen, signature, 0, NULL);
    g_assert_cmpint(g_menu_model_get_n_items(G_MENU_MODEL(flat)), ==, expected);
    g_string_free(signature, TRUE);
    g_hash_table_unref(seen);
    g_object_unref(flat);
}

static void duplicate_export_sections(void) {
    GMenu *root = g_menu_new();
    GMenu *section = section_with_item("File", "win.file");
    g_menu_append_section(root, NULL, G_MENU_MODEL(section));
    g_menu_append_section(root, NULL, G_MENU_MODEL(section));
    verify_count(root, 1);
    g_object_unref(section);
    g_object_unref(root);
}

static void independent_actions_with_the_same_label(void) {
    GMenu *root = g_menu_new();
    GMenu *one = section_with_item("Tools", "win.tools");
    GMenu *two = section_with_item("Tools", "win.addon");
    g_menu_append_section(root, NULL, G_MENU_MODEL(one));
    g_menu_append_section(root, NULL, G_MENU_MODEL(two));
    verify_count(root, 2);
    g_object_unref(one);
    g_object_unref(two);
    g_object_unref(root);
}

static void root_command_is_preserved(void) {
    GMenu *root = g_menu_new();
    g_menu_append(root, "About", "win.about");
    verify_count(root, 1);
    g_object_unref(root);
}

int main(int argc, char **argv) {
    g_test_init(&argc, &argv, NULL);
    g_test_add_func("/native-header/menu/duplicate-sections", duplicate_export_sections);
    g_test_add_func("/native-header/menu/distinct-actions", independent_actions_with_the_same_label);
    g_test_add_func("/native-header/menu/root-command", root_command_is_preserved);
    return g_test_run();
}
