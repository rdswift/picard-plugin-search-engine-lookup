# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021, 2025 Bob Swift (rdswift)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.


import re
from urllib.parse import quote_plus
from uuid import uuid4

from PyQt6 import QtCore, QtGui, QtWidgets

from picard.plugin3.api import (
    BaseAction,
    Cluster,
    OptionsPage,
    PluginApi,
    t_,
)

from .ui_options_search_engine_lookup import Ui_SearchEngineLookupOptionsPage

from picard.util.webbrowser2 import open as _open


USER_GUIDE_URL = 'https://picard-plugins-user-guides.readthedocs.io/en/latest/search_engine_lookup/user_guide.html'

DEFAULT_PROVIDERS = {
    'ea520f49-36bc-4821-a16a-38bf0340d1f3': {'name': 'Google', 'url': r'https://www.google.com/search?q=%search%'},
    '7b93d4b5-34d9-49a7-901c-ed0914f07aee': {'name': 'Bing', 'url': r'https://www.bing.com/search?q=%search%'},
    '37be75d9-5fc5-4858-87fc-b5db0896a163': {'name': 'DuckDuckGo', 'url': r'https://duckduckgo.com/?q=%search%'},
}

DEFAULT_PROVIDER = 'ea520f49-36bc-4821-a16a-38bf0340d1f3'
DEFAULT_EXTRA_WORDS = 'album'

RE_VALIDATE_TITLE = re.compile(r'^[^\s"|][^"|]*[^\s"|]$')
RE_VALIDATE_URL = re.compile(r'^[^\s"]*%search%[^\s"]*$')

KEY_PROVIDER = 'search_engine_lookup_provider'
KEY_PROVIDERS = 'search_engine_lookup_providers'
KEY_EXTRA = 'search_engine_lookup_extra_words'


def show_popup(title='', content='', window=None):
    QtWidgets.QMessageBox.information(
        window,
        title,
        content,
        QtWidgets.QMessageBox.StandardButton.Ok,
        QtWidgets.QMessageBox.StandardButton.Ok
    )


class SearchEngineLookup:
    api = None

    @classmethod
    def initialize(cls, api: PluginApi):
        cls.api = api

    @classmethod
    def lookup_error(cls):
        cls.api.logger.error("No existing metadata to lookup.")
        show_popup(
            cls.api.tr('message.lookup_error.title', 'Lookup Error'),
            cls.api.tr('message.lookup_error.text', 'There is no existing data to use for a search.')
        )

    @classmethod
    def do_lookup(cls, text):
        provider = cls.api.plugin_config[KEY_PROVIDER]
        providers = cls.api.plugin_config[KEY_PROVIDERS]
        selected_provider: dict = providers[provider] if provider in providers else DEFAULT_PROVIDERS[DEFAULT_PROVIDER]
        base_url: str = selected_provider['url']
        url: str = base_url.replace(r'%search%', quote_plus(text))
        cls.api.logger.debug("Looking up %s", url)
        _open(url)

    @classmethod
    def lookup_cover_art(cls, title, artist):
        text = f"{title} by {artist} album cover"
        cls.do_lookup(text)


class ClusterLookup(BaseAction):
    TITLE = t_('action.title.cluster', "Search engine lookup")

    def callback(self, cluster_list):
        extra = self.api.plugin_config[KEY_EXTRA].split()
        for cluster in cluster_list:
            if isinstance(cluster, Cluster):
                parts = []
                if 'albumartist' in cluster.metadata and cluster.metadata['albumartist']:
                    parts.extend(cluster.metadata['albumartist'].split())
                if 'album' in cluster.metadata and cluster.metadata['albumartist']:
                    parts.extend(cluster.metadata['album'].split())
                if parts:
                    if extra:
                        parts.extend(extra)
                    text = ' '.join(parts)
                    SearchEngineLookup.do_lookup(text)
                else:
                    SearchEngineLookup.lookup_error()
            else:
                self.api.logger.error("Argument is not a cluster. %s", cluster)
                show_popup(
                    self.api.tr('message.cluster_error.title', 'Lookup Error'),
                    self.api.tr('message.cluster_error.text', 'There was a problem with the information provided for the cluster.')
                )


class AlbumCoverArtLookup(BaseAction):
    TITLE = t_('action.title.album', "Album cover art lookup")

    def callback(self, album):
        metadata = album[0].metadata
        if 'album' in metadata and 'albumartist' in metadata:
            SearchEngineLookup.lookup_cover_art(metadata['album'], metadata['albumartist'])
        else:
            SearchEngineLookup.lookup_error()


class TrackCoverArtLookup(BaseAction):
    TITLE = t_('action.title.track', "Track cover art lookup")

    def callback(self, track):
        metadata = track[0].metadata
        if 'title' in metadata and 'artist' in metadata:
            SearchEngineLookup.lookup_cover_art(metadata['title'], metadata['artist'])
        else:
            SearchEngineLookup.lookup_error()


class SearchEngineEditDialog(QtWidgets.QDialog):

    def __init__(self, parent=None, edit_provider='', edit_url='', titles=None, api: PluginApi = None):
        super().__init__(parent)
        self.api = api
        self.parent = parent
        self.output = None
        self.edit_provider = edit_provider
        self.edit_url = edit_url
        self.providers = titles if titles else []

        self.valid_no = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton).pixmap(16, 16)
        self.valid_yes = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton).pixmap(16, 16)

        self.setup_ui()
        self.setup_actions()
        self.check_validation()

    def setup_ui(self):
        self.setWindowTitle(self.api.tr("EditorDialog.window.title", "Edit Search Engine Provider"))
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.verticalLayout = QtWidgets.QVBoxLayout(self)

        self.description = QtWidgets.QLabel()
        self.description.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.description.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeading | QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.description.setWordWrap(True)
        self.verticalLayout.addWidget(self.description)

        spacer = QtWidgets.QSpacerItem(20, 6, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed)
        self.verticalLayout.addSpacerItem(spacer)

        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setContentsMargins(-1, -1, -1, 0)
        self.label_title = QtWidgets.QLabel()
        self.gridLayout.addWidget(self.label_title, 0, 0, 1, 1)
        self.label_url = QtWidgets.QLabel()
        self.gridLayout.addWidget(self.label_url, 1, 0, 1, 1)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.le_title = QtWidgets.QLineEdit()
        self.le_title.setMinimumWidth(400)
        self.le_title.setFont(font)
        self.gridLayout.addWidget(self.le_title, 0, 1, 1, 1)
        self.le_url = QtWidgets.QLineEdit()
        self.le_url.setMinimumWidth(400)
        self.le_url.setFont(font)
        self.gridLayout.addWidget(self.le_url, 1, 1, 1, 1)
        self.img_valid_title = QtWidgets.QLabel()
        self.img_valid_title.setMinimumSize(QtCore.QSize(16, 16))
        self.img_valid_title.setText("")
        self.gridLayout.addWidget(self.img_valid_title, 0, 2, 1, 1)
        self.img_valid_url = QtWidgets.QLabel()
        self.img_valid_url.setMinimumSize(QtCore.QSize(16, 16))
        self.img_valid_url.setText("")
        self.gridLayout.addWidget(self.img_valid_url, 1, 2, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)

        self.buttonBox = QtWidgets.QDialogButtonBox()
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.verticalLayout.addWidget(self.buttonBox)

        self.description.setText(self.api.tr(
            "EditorDialog.label.description",
            (
                "Enter the title and URL for the search engine provider. Titles must be at least two non-space characters long, and "
                "must not be the same as the title of an existing provider.\n\nWhen entering the URL the macro **%search%** must be "
                "included. This will be replaced by the list of search words separated by plus signs when the url is sent to your "
                "browser for display."
            )
        ))
        self.label_title.setText(self.api.tr("EditorDialog.label.title", "Title:"))
        self.label_url.setText(self.api.tr("EditorDialog.label.url", "URL:"))
        self.le_title.setToolTip(self.api.tr("EditorDialog.tooltip.title", "The title to show in the list for the search engine provider"))
        self.le_url.setToolTip(self.api.tr("EditorDialog.tooltip.url", "The URL to use for the search engine provider"))

        self.le_title.setText(self.edit_provider)
        self.le_url.setText(self.edit_url)

    def setup_actions(self):
        self.le_title.textChanged.connect(self.title_text_changed)
        self.le_url.textChanged.connect(self.url_text_changed)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def check_validation(self):
        valid_title = re.match(RE_VALIDATE_TITLE, self.edit_provider) and self.edit_provider not in self.providers
        self.img_valid_title.setPixmap(self.valid_yes if valid_title else self.valid_no)

        valid_url = re.match(RE_VALIDATE_URL, self.edit_url)
        self.img_valid_url.setPixmap(self.valid_yes if valid_url else self.valid_no)

        # Note that this needs to be forced to a bool to avoid Qt crashing Picard
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(bool(valid_title and valid_url))

    def get_output(self):
        return self.output

    def accept(self):
        self.output = (self.edit_provider.strip(), self.edit_url.strip())
        super().accept()

    def title_text_changed(self, text):
        self.edit_provider = text
        self.check_validation()

    def url_text_changed(self, text):
        self.edit_url = text
        self.check_validation()


class SearchEngineLookupOptionsPage(OptionsPage):

    TITLE = t_('ui.options.title', "Search Engine Lookup")
    HELP_URL = USER_GUIDE_URL

    def __init__(self, parent=None):
        super(SearchEngineLookupOptionsPage, self).__init__(parent)
        self.ui = Ui_SearchEngineLookupOptionsPage()
        self.ui.setupUi(self)
        self.setup_actions()
        self.provider = ''
        self.providers = {}
        self.additional_words = ''

    def setup_actions(self):
        self.ui.providers.itemChanged.connect(self.select_provider)
        self.ui.pb_add.clicked.connect(self.add_provider)
        self.ui.pb_edit.clicked.connect(self.edit_provider)
        self.ui.pb_delete.clicked.connect(self.delete_provider)
        self.ui.pb_test.clicked.connect(self.test_provider)
        self.ui.le_additional_words.textChanged.connect(self.edit_additional_words)

    def load(self):
        # Settings for search engine providers
        self.providers = self.api.plugin_config[KEY_PROVIDERS] or DEFAULT_PROVIDERS.copy()

        # Settings for search engine provider
        self.provider = self.api.plugin_config[KEY_PROVIDER]
        if self.provider not in self.providers:
            # Assign an arbitrary valid value to self.provider
            self.provider = list(self.providers)[0]

        # Settings for search extra words
        self.additional_words = self.api.plugin_config[KEY_EXTRA]
        self.ui.le_additional_words.setText(self.additional_words)

        # Display list of providers
        self.update_list()

    def select_provider(self, list_item: QtWidgets.QListWidgetItem):
        if list_item.checkState() == QtCore.Qt.CheckState.Checked:
            # New provider selected
            self.provider = list_item.data(QtCore.Qt.ItemDataRole.UserRole)
            self.update_list(current_item=self.provider)
        else:
            # Attempt to deselect the current provider leaving none selected
            list_item.setCheckState(QtCore.Qt.CheckState.Checked)

    def add_provider(self):
        provider_id = uuid4()
        self.edit_provider_dialog(provider_id)

    def edit_additional_words(self):
        self.additional_words = self.ui.le_additional_words.text().strip()

    def edit_provider(self):
        current_item = self.ui.providers.currentItem()
        provider = current_item.text()
        provider_id = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
        url = self.providers[provider_id]['url']
        self.edit_provider_dialog(provider_id, provider, url)

    def edit_provider_dialog(self, provider_id='', provider='', url=''):
        # List of titles currently used and not allowed.  Omit current title from the list when editing.
        titles = [x['name'] for x in self.providers.values() if x['name'] != provider]
        dialog = SearchEngineEditDialog(parent=self, edit_provider=provider, edit_url=url, titles=titles, api=self.api)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            data = dialog.get_output()
            if data:
                new_provider, new_url = data
                self.providers[provider_id] = {'name': new_provider, 'url': new_url}
                self.update_list(provider_id)

    def delete_provider(self):
        current_item = self.ui.providers.currentItem()
        provider = current_item.text()
        provider_id = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
        if current_item.checkState() or provider_id == self.provider:
            QtWidgets.QMessageBox.critical(
                self,
                self.api.tr('ui.dialog.deletion_error.title', 'Deletion Error'),
                self.api.tr('ui.dialog.deletion_error.text', 'You cannot delete the currently selected search provider.'),
                QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Ok
            )
        else:
            if QtWidgets.QMessageBox.warning(
                self,
                self.api.tr('ui.dialog.confirm_deletion.title','Confirm Deletion'),
                self.api.tr(
                    'ui.dialog.confirm_deletion.text',
                    'You are about to permanently delete the search provider "{provider_name}".  Continue?'
                ).format(provider_name=provider),
                QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel
            ) == QtWidgets.QMessageBox.StandardButton.Ok:
                self.providers.pop(provider_id, None)
                self.update_list()

    def test_provider(self):
        current_item = self.ui.providers.currentItem()
        parts = ('The Beatles Abby Road ' + self.additional_words).strip().split()
        url = self.providers[current_item.data(QtCore.Qt.ItemDataRole.UserRole)]['url'].replace(r'%search%', quote_plus(' '.join(parts)))
        _open(url)

    def update_list(self, current_item=None):
        current_row = -1
        self.ui.providers.clear()
        for counter, provider_id in enumerate(self.providers):
            item = QtWidgets.QListWidgetItem()
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setText(self.providers[provider_id]['name'])
            item.setCheckState(QtCore.Qt.CheckState.Checked if provider_id == self.provider else QtCore.Qt.CheckState.Unchecked)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, provider_id)
            self.ui.providers.addItem(item)
            if current_item and provider_id == current_item:
                current_row = counter
        current_row = max(current_row, 0)
        self.ui.providers.setCurrentRow(current_row)
        self.ui.providers.sortItems()

    def save(self):
        self._set_settings(self.api.plugin_config)

    def _set_settings(self, settings):
        settings[KEY_PROVIDER] = self.provider.strip()
        settings[KEY_EXTRA] = self.additional_words.strip()
        settings[KEY_PROVIDERS] = self.providers or DEFAULT_PROVIDERS.copy()


def enable(api: PluginApi):
    """Called when plugin is enabled."""

    # Initialize lookup class
    SearchEngineLookup.initialize(api)

    # Register configuration options
    api.plugin_config.register_option(KEY_PROVIDERS, DEFAULT_PROVIDERS.copy())
    api.plugin_config.register_option(KEY_PROVIDER, DEFAULT_PROVIDER)
    api.plugin_config.register_option(KEY_EXTRA, DEFAULT_EXTRA_WORDS)

    # Migrate settings from 2.x version if available
    migrate_settings(api)

    # Register actions
    api.register_cluster_action(ClusterLookup)
    api.register_album_action(AlbumCoverArtLookup)
    api.register_track_action(TrackCoverArtLookup)

    # Register options page
    api.register_options_page(SearchEngineLookupOptionsPage)


def migrate_settings(api: PluginApi):
    if api.global_config.setting.raw_value(KEY_PROVIDERS) is None:
        return

    api.logger.info("Migrating settings from 2.x version.")

    mapping = [
        (KEY_EXTRA, str),
        (KEY_PROVIDER, str),
        (KEY_PROVIDERS, dict),
    ]

    for key, qtype in mapping:
        if api.global_config.setting.raw_value(key) is None:
            api.logger.debug("No old setting for key: '%s'", key,)
            continue
        api.plugin_config[key] = api.global_config.setting.raw_value(key, qtype=qtype)
        api.global_config.setting.remove(key)
