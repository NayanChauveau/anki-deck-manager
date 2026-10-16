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
    QPushButton,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import askUser, openLink, showInfo, showWarning

from .domain import GithubSource, UrlError, parse_github_url, status_of
from .github import GithubError, fetch_release
from .manager import (
    AssetNotInRelease,
    check_catalog,
    configured_max_bytes,
    is_duplicate,
    make_subscription,
)
from .runner import start_installs
from .store import (
    CONFIG_KEY,
    Catalog,
    DuplicateSubscription,
    add_subscription,
    dump_catalog,
    load_catalog,
    remove_subscription,
)
from . import strings

_dialog: ManagerDialog | None = None


def register() -> None:
    gui_hooks.main_window_did_init.append(_add_menu)
    gui_hooks.profile_will_close.append(_close_dialog)


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


def _close_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
        _dialog = None


class ManagerDialog(QDialog):
    def __init__(self, parent: object) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._busy = False
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
        if self._busy:
            return
        dialog = AddDialog(self, _read_catalog())
        if dialog.exec() and dialog.subscription_id:
            self.refresh()
            self._install([dialog.subscription_id])

    def _check(self) -> None:
        if self._busy:
            return
        catalog = _read_catalog()
        if not catalog.subscriptions:
            return
        self._busy = True
        checked_at = _now()

        def op(_col: object) -> Catalog:
            return check_catalog(catalog, _fetch_latest, checked_at)

        def success(updated: Catalog) -> None:
            _write_catalog(updated)
            self._busy = False
            self.refresh()

        def failure(_exc: Exception) -> None:
            self._busy = False
            showWarning(strings.error_text("http_error"), parent=self, title=strings.WINDOW_TITLE)

        (
            QueryOp(parent=self, op=op, success=success)
            .failure(failure)
            .without_collection()
            .run_in_background()
        )

    def _import(self) -> None:
        if self._busy:
            return
        catalog = _read_catalog()
        chosen = self._selected_ids() or [item.id for item in catalog.subscriptions]
        pending = [
            subscription.id
            for subscription in catalog.subscriptions
            if subscription.id in chosen and status_of(subscription) == "update_available"
        ]
        if not pending:
            showInfo(strings.NO_UPDATE, parent=self, title=strings.WINDOW_TITLE)
            return
        self._install(pending)

    def _install(self, subscription_ids: list[str]) -> None:
        self._busy = True
        catalog = _read_catalog()
        config = mw.addonManager.getConfig("deck_manager")

        def finished(updated: Catalog) -> None:
            _write_catalog(updated)
            self._busy = False
            self.refresh()

        start_installs(
            mw,
            catalog,
            subscription_ids,
            max_bytes=configured_max_bytes(config),
            on_finished=finished,
        )

    def _open_repo(self) -> None:
        subscription = self._one_selected()
        if subscription is None:
            return
        openLink(subscription.repo_url)

    def _remove(self) -> None:
        if self._busy:
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
            result = fetch_release(source, latest=False)
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
                updated = add_subscription(self._catalog, subscription)
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
    source = GithubSource(
        owner=owner,
        repository=repository,
        repo_url=f"https://github.com/{owner}/{repository}",
        version="0.0.0",
        asset_name="deck.apkg",
    )
    return fetch_release(source, latest=True, etag=etag)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    from uuid import uuid4

    return uuid4().hex
