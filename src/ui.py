"""Deck Manager window. Qt comes from aqt.qt and is not imported by tests."""

from __future__ import annotations

from datetime import datetime, timezone

from aqt import gui_hooks, mw
from aqt.operations import QueryOp
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QTimer,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import askUser, openLink, showInfo, showWarning

from .domain import GithubSource, UrlError, parse_github_url
from .github import GithubError, fetch_latest, fetch_tag
from .manager import (
    AssetNotInRelease,
    check_catalog,
    configured_interval_hours,
    configured_max_bytes,
    due_repositories,
    is_duplicate,
    make_subscription,
    pending_updates,
)
from .runner import start_installs
from .store import (
    CONFIG_KEY,
    Catalog,
    DuplicateSubscription,
    add_subscription,
    dump_catalog,
    load_catalog,
    merge_checked,
    merge_installed,
    remove_subscription,
)
from . import strings

_dialog: ManagerDialog | None = None
_startup_started = False
_busy = False
_epoch = 0


def register() -> None:
    gui_hooks.main_window_did_init.append(_add_menu)
    gui_hooks.profile_did_open.append(_schedule_startup)
    gui_hooks.profile_will_close.append(_close_profile)


def _add_menu() -> None:
    action = QAction(strings.MENU, mw)
    qconnect(action.triggered, open_manager)
    mw.form.menuTools.addAction(action)


def open_manager(*_args: object) -> None:
    global _dialog
    if mw.col is None:
        showInfo(strings.NO_PROFILE, parent=mw, title=strings.WINDOW_TITLE)
        return
    if _dialog is None:
        _dialog = ManagerDialog(mw)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    _dialog.refresh()


def _close_profile() -> None:
    global _startup_started, _epoch
    _startup_started = False
    _epoch += 1
    _set_busy(False)
    _close_dialog()


def _close_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
        _dialog = None


def _schedule_startup() -> None:
    # profile_did_open runs while the main window is still settling.
    QTimer.singleShot(0, _startup_check)


def _startup_check() -> None:
    global _startup_started
    if _startup_started or _busy or mw.col is None:
        return
    _startup_started = True
    collection = mw.col
    epoch = _epoch
    try:
        catalog = _read_catalog()
        config = mw.addonManager.getConfig("deck_manager")
        due = due_repositories(
            catalog,
            datetime.now(timezone.utc),
            configured_interval_hours(config),
        )
        if not due:
            _offer_updates(catalog, collection, epoch)
            return
    except Exception:
        return

    baseline_ids = {item.id for item in catalog.subscriptions}
    _set_busy(True)

    def op(_col: object) -> Catalog:
        return check_catalog(catalog, _fetch_latest, _now(), only=due)

    def success(updated: Catalog) -> None:
        if _epoch != epoch:
            return
        _finish_check(collection, baseline_ids, updated)
        _set_busy(False)
        if mw.col is collection:
            _offer_updates(_read_catalog(), collection, epoch)

    def failure(_exc: Exception) -> None:
        if _epoch != epoch:
            return
        _set_busy(False)
        if mw.col is collection:
            _offer_updates(_read_catalog(), collection, epoch)

    (
        QueryOp(parent=mw, op=op, success=success)
        .failure(failure)
        .without_collection()
        .run_in_background()
    )


def _offer_updates(catalog: Catalog, collection: object, epoch: int) -> None:
    if _busy or _epoch != epoch or mw.col is not collection:
        return
    updates = pending_updates(catalog)
    if not updates:
        return
    _set_busy(True)
    chosen = _ask_updates(updates)
    if _epoch != epoch:
        return
    _set_busy(False)
    if chosen and mw.col is collection:
        _start_install(list(chosen), collection)


def _ask_updates(updates: tuple) -> list[str]:
    notice = UpdateNotice(mw, updates)
    if not notice.exec():
        return []
    return notice.chosen_ids()


def _start_install(subscription_ids: list[str], collection: object) -> None:
    if _busy or mw.col is not collection:
        return
    catalog = _read_catalog()
    baseline_ids = {item.id for item in catalog.subscriptions}
    config = mw.addonManager.getConfig("deck_manager")
    epoch = _epoch
    _set_busy(True)

    def finished(updated: Catalog) -> None:
        if _epoch != epoch or mw.col is not collection:
            return
        try:
            _write_catalog(merge_installed(_read_catalog(), baseline_ids, updated))
            if _dialog is not None:
                _dialog.refresh()
        finally:
            _set_busy(False)

    start_installs(
        mw,
        catalog,
        subscription_ids,
        max_bytes=configured_max_bytes(config),
        on_finished=finished,
    )


def _finish_check(collection: object, baseline_ids: set[str], updated: Catalog) -> None:
    if mw.col is not collection:
        return
    try:
        _write_catalog(merge_checked(_read_catalog(), baseline_ids, updated))
        if _dialog is not None:
            _dialog.refresh()
    except Exception:
        return


def _set_busy(busy: bool) -> None:
    global _busy
    _busy = busy
    if _dialog is not None:
        _dialog._busy = busy


class ManagerDialog(QDialog):
    def __init__(self, parent: object) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._busy = _busy
        self.setWindowTitle(strings.WINDOW_TITLE)
        self.resize(760, 420)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [
                strings.COLUMN_DECK,
                strings.COLUMN_SOURCE,
                strings.COLUMN_VERSION,
                strings.COLUMN_STATUS,
            ]
        )
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        self.empty = QLabel(strings.EMPTY)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.add_button = QPushButton(strings.ADD)
        self.check_button = QPushButton(strings.CHECK)
        self.import_button = QPushButton(strings.IMPORT)
        self.open_button = QPushButton(strings.OPEN_REPO)
        self.remove_button = QPushButton(strings.REMOVE)
        qconnect(self.add_button.clicked, self._add)
        qconnect(self.check_button.clicked, self._check)
        qconnect(self.import_button.clicked, self._import)
        qconnect(self.open_button.clicked, self._open_repo)
        qconnect(self.remove_button.clicked, self._remove)

        buttons = QHBoxLayout()
        for button in (
            self.add_button,
            self.check_button,
            self.import_button,
            self.open_button,
            self.remove_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.empty)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        catalog = _read_catalog()
        selected = set(self._selected_ids())
        self.table.setRowCount(len(catalog.subscriptions))
        for row, subscription in enumerate(catalog.subscriptions):
            values = (
                subscription.display_name,
                strings.source_text(subscription),
                strings.version_text(subscription),
                strings.status_text(subscription),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, subscription.id)
                self.table.setItem(row, column, item)
            if subscription.id in selected:
                self.table.selectRow(row)
        self.empty.setVisible(not catalog.subscriptions)

    def _add(self) -> None:
        if _busy or mw.col is None:
            return
        dialog = AddDialog(self, _read_catalog())
        if dialog.exec() and dialog.subscription_id:
            self.refresh()
            _start_install([dialog.subscription_id], mw.col)

    def _check(self) -> None:
        if _busy or mw.col is None:
            return
        catalog = _read_catalog()
        if not catalog.subscriptions:
            return
        collection = mw.col
        baseline_ids = {item.id for item in catalog.subscriptions}
        checked_at = _now()
        epoch = _epoch
        _set_busy(True)

        def op(_col: object) -> Catalog:
            return check_catalog(catalog, _fetch_latest, checked_at)

        def success(updated: Catalog) -> None:
            if _epoch != epoch:
                return
            _finish_check(collection, baseline_ids, updated)
            _set_busy(False)

        def failure(_exc: Exception) -> None:
            if _epoch != epoch:
                return
            _set_busy(False)
            if mw.col is collection:
                showWarning(strings.error_text("http_error"), parent=self, title=strings.WINDOW_TITLE)

        (
            QueryOp(parent=self, op=op, success=success)
            .failure(failure)
            .without_collection()
            .run_in_background()
        )

    def _import(self) -> None:
        if _busy or mw.col is None:
            return
        catalog = _read_catalog()
        chosen = self._selected_ids() or [item.id for item in catalog.subscriptions]
        pending = [
            subscription.id
            for subscription in catalog.subscriptions
            if subscription.id in chosen and subscription.available_version
        ]
        if not pending:
            showInfo(strings.NO_UPDATE, parent=self, title=strings.WINDOW_TITLE)
            return
        _start_install(pending, mw.col)

    def _open_repo(self) -> None:
        subscription = self._one_selected()
        if subscription is None:
            return
        openLink(subscription.repo_url)

    def _remove(self) -> None:
        if _busy:
            return
        ids = self._selected_ids()
        catalog = _read_catalog()
        chosen = [item for item in catalog.subscriptions if item.id in ids]
        if not chosen:
            showInfo(strings.NO_SELECTION, parent=self, title=strings.WINDOW_TITLE)
            return
        # The Anki deck is not deleted. Only the subscription leaves the catalog.
        if not askUser(
            strings.removal_message([item.display_name for item in chosen]),
            parent=self,
            defaultno=True,
            title=strings.WINDOW_TITLE,
        ):
            return
        for subscription in chosen:
            catalog = remove_subscription(catalog, subscription.id)
        _write_catalog(catalog)
        self.refresh()

    def _selected_ids(self) -> list[str]:
        rows = sorted({item.row() for item in self.table.selectedItems()})
        ids: list[str] = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(value, str):
                    ids.append(value)
        return ids

    def _one_selected(self):
        ids = self._selected_ids()
        if len(ids) != 1:
            showInfo(strings.NO_SELECTION, parent=self, title=strings.WINDOW_TITLE)
            return None
        return next((item for item in _read_catalog().subscriptions if item.id == ids[0]), None)


class UpdateNotice(QDialog):
    def __init__(self, parent: object, updates: tuple) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._updates = updates
        self.setWindowTitle(strings.updates_title(len(updates)))
        self.resize(480, 220 if len(updates) > 1 else 140)
        layout = QVBoxLayout(self)
        if len(updates) == 1:
            notice = QLabel(strings.update_notice(updates[0]))
            notice.setWordWrap(True)
            layout.addWidget(notice)
            self._list = None
        else:
            heading = QLabel(strings.updates_title(len(updates)))
            layout.addWidget(heading)
            self._list = QListWidget()
            for subscription in updates:
                item = QListWidgetItem(strings.update_notice(subscription))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, subscription.id)
                self._list.addItem(item)
            layout.addWidget(self._list)
        later = QPushButton(strings.LATER)
        later.setDefault(True)
        install = QPushButton(strings.IMPORT)
        qconnect(later.clicked, self.reject)
        qconnect(install.clicked, self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(later)
        buttons.addWidget(install)
        layout.addLayout(buttons)

    def chosen_ids(self) -> list[str]:
        if self._list is None:
            return [self._updates[0].id]
        chosen: list[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                value = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(value, str):
                    chosen.append(value)
        return chosen


class AddDialog(QDialog):
    def __init__(self, parent: QDialog, catalog: Catalog) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self.subscription_id: str | None = None
        self.setWindowTitle(strings.ADD_TITLE)
        self.resize(560, 160)
        self.help = QLabel(strings.ADD_HELP)
        self.help.setWordWrap(True)
        self.url = QLineEdit()
        self.url.setPlaceholderText(strings.ADD_PLACEHOLDER)
        self.add_button = QPushButton(strings.ADD)
        self.cancel_button = QPushButton(strings.CANCEL)
        qconnect(self.add_button.clicked, self._submit)
        qconnect(self.cancel_button.clicked, self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.add_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.help)
        layout.addWidget(self.url)
        layout.addLayout(buttons)

    def _submit(self) -> None:
        try:
            source = parse_github_url(self.url.text())
        except UrlError as exc:
            showWarning(strings.url_error_text(exc.code), parent=self, title=strings.ADD_TITLE)
            return
        if is_duplicate(self._catalog, source):
            showWarning(strings.DUPLICATE, parent=self, title=strings.ADD_TITLE)
            return
        self.add_button.setEnabled(False)

        def op(_col: object) -> tuple[GithubSource, object]:
            result = fetch_tag(source.owner, source.repository, source.version)
            if result.release is None:
                raise GithubError("http_error")
            return source, result.release

        def success(payload: tuple[GithubSource, object]) -> None:
            source, release = payload
            try:
                subscription = make_subscription(source, release, _new_id())  # type: ignore[arg-type]
            except AssetNotInRelease:
                self.add_button.setEnabled(True)
                showWarning(strings.ASSET_MISSING, parent=self, title=strings.ADD_TITLE)
                return
            try:
                updated = add_subscription(_read_catalog(), subscription)
            except DuplicateSubscription:
                self.add_button.setEnabled(True)
                showWarning(strings.DUPLICATE, parent=self, title=strings.ADD_TITLE)
                return
            _write_catalog(updated)
            self.subscription_id = subscription.id
            self.accept()

        def failure(exc: Exception) -> None:
            self.add_button.setEnabled(True)
            code = exc.code if isinstance(exc, GithubError) else "http_error"
            showWarning(strings.error_text(code), parent=self, title=strings.ADD_TITLE)

        (
            QueryOp(parent=self, op=op, success=success)
            .failure(failure)
            .without_collection()
            .run_in_background()
        )


def _read_catalog() -> Catalog:
    if mw.col is None:
        return load_catalog(None)
    return load_catalog(mw.col.get_config(CONFIG_KEY, None))


def _write_catalog(catalog: Catalog) -> None:
    if mw.col is None:
        return
    mw.col.set_config(CONFIG_KEY, dump_catalog(catalog), undoable=False)


def _fetch_latest(owner: str, repository: str, etag: str | None):
    return fetch_latest(owner, repository, etag=etag)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    from uuid import uuid4

    return uuid4().hex
