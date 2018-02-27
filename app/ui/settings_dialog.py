from app.properties import write_config, Profile, get_default_settings
from . import Gtk, UI_RESOURCES_PATH
from .main_helper import update_entry_data


def show_settings_dialog(transient, options):
    return SettingsDialog(transient, options).show()


class SettingsDialog:
    def __init__(self, transient, options):
        handlers = {"on_data_dir_field_icon_press": self.on_data_dir_field_icon_press,
                    "on_picons_dir_field_icon_press": self.on_picons_dir_field_icon_press,
                    "on_profile_changed": self.on_profile_changed,
                    "on_reset": self.on_reset,
                    "apply_settings": self.apply_settings}

        builder = Gtk.Builder()
        builder.set_translation_domain("demon-editor")
        builder.add_objects_from_file(UI_RESOURCES_PATH + "dialogs.glade",
                                      ("settings_dialog", "telnet_timeout_adjustment"))
        builder.connect_signals(handlers)

        self._dialog = builder.get_object("settings_dialog")
        self._dialog.set_transient_for(transient)
        self._host_field = builder.get_object("host_field")
        self._port_field = builder.get_object("port_field")
        self._login_field = builder.get_object("login_field")
        self._password_field = builder.get_object("password_field")
        self._telnet_login_field = builder.get_object("telnet_login_field")
        self._telnet_password_field = builder.get_object("telnet_password_field")
        self._telnet_port_field = builder.get_object("telnet_port_field")
        self._telnet_timeout_spin_button = builder.get_object("telnet_timeout_spin_button")
        self._services_field = builder.get_object("services_field")
        self._user_bouquet_field = builder.get_object("user_bouquet_field")
        self._satellites_xml_field = builder.get_object("satellites_xml_field")
        self._data_dir_field = builder.get_object("data_dir_field")
        self._picons_field = builder.get_object("picons_field")
        self._picons_dir_field = builder.get_object("picons_dir_field")
        self._enigma_radio_button = builder.get_object("enigma_radio_button")
        self._neutrino_radio_button = builder.get_object("neutrino_radio_button")

        self._options = options
        self._active_profile = options.get("profile")
        self.set_settings()
        self._neutrino_radio_button.set_active(Profile(self._active_profile) is Profile.NEUTRINO_MP)

    def show(self):
        response = self._dialog.run()
        if response == Gtk.ResponseType.OK:
            self.apply_settings()
            write_config(self._options)
        self._dialog.destroy()

        return response

    def on_data_dir_field_icon_press(self, entry, icon, event_button):
        update_entry_data(entry, self._dialog, self._options.get(self._options.get("profile")))

    def on_picons_dir_field_icon_press(self, entry, icon, event_button):
        update_entry_data(entry, self._dialog, self._options.get(self._options.get("profile")))

    def on_profile_changed(self, item):
        self.set_profile(Profile.ENIGMA_2 if self._enigma_radio_button.get_active() else Profile.NEUTRINO_MP)

    def set_profile(self, profile):
        self._active_profile = profile.value
        self.set_settings()

    def on_reset(self, item):
        def_settings = get_default_settings()
        for key in def_settings:
            current = self._options.get(key)
            if type(current) is str:
                continue
            default = def_settings.get(key)
            for k in default:
                current[k] = default.get(k)
        self.set_settings()

    def set_settings(self):
        options = self._options.get(self._active_profile)
        self._host_field.set_text(options.get("host", ""))
        self._port_field.set_text(options.get("port", ""))
        self._login_field.set_text(options.get("user", ""))
        self._password_field.set_text(options.get("password", ""))
        self._telnet_login_field.set_text(options.get("telnet_user", ""))
        self._telnet_password_field.set_text(options.get("telnet_password", ""))
        self._telnet_port_field.set_text(options.get("telnet_port", ""))
        self._telnet_timeout_spin_button.set_value(options.get("telnet_timeout", 5))
        self._services_field.set_text(options.get("services_path", ""))
        self._user_bouquet_field.set_text(options.get("user_bouquet_path", ""))
        self._satellites_xml_field.set_text(options.get("satellites_xml_path", ""))
        self._picons_field.set_text(options.get("picons_path", ""))
        self._data_dir_field.set_text(options.get("data_dir_path", ""))
        self._picons_dir_field.set_text(options.get("picons_dir_path", ""))

    def apply_settings(self, item=None):
        profile = Profile.ENIGMA_2.value if self._enigma_radio_button.get_active() else Profile.NEUTRINO_MP.value
        self._active_profile = profile
        self._options["profile"] = profile
        options = self._options.get(self._active_profile)
        options["host"] = self._host_field.get_text()
        options["port"] = self._port_field.get_text()
        options["user"] = self._login_field.get_text()
        options["password"] = self._password_field.get_text()
        options["telnet_user"] = self._telnet_login_field.get_text()
        options["telnet_password"] = self._telnet_password_field.get_text()
        options["telnet_port"] = self._telnet_port_field.get_text()
        options["telnet_timeout"] = int(self._telnet_timeout_spin_button.get_value())
        options["services_path"] = self._services_field.get_text()
        options["user_bouquet_path"] = self._user_bouquet_field.get_text()
        options["satellites_xml_path"] = self._satellites_xml_field.get_text()
        options["picons_path"] = self._picons_field.get_text()
        options["data_dir_path"] = self._data_dir_field.get_text()
        options["picons_dir_path"] = self._picons_dir_field.get_text()


if __name__ == "__main__":
    pass
