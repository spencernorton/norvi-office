"""User-granted access to one open Calc or Writer document."""
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
from threading import Event, Lock, Thread
from time import monotonic

import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK, BUTTONS_YES_NO, DEFAULT_BUTTON_NO
from com.sun.star.awt.MessageBoxResults import YES
from com.sun.star.awt.MessageBoxType import INFOBOX, QUERYBOX
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization

IMPLEMENTATION = "dev.norvi.OfficeLiveTools"
START = "dev.norvi.office:share"
STOP = "dev.norvi.office:stop"
TIME_LIMIT = 30 * 60
REQUEST_LIMIT = 128 * 1024
CALC = "com.sun.star.sheet.SpreadsheetDocument"
WRITER = "com.sun.star.text.TextDocument"
CELL = r"[A-Z]{1,3}[1-9][0-9]{0,6}"
RANGE = re.compile(rf"{CELL}(?::{CELL})?")
FORMULA = re.compile(rf"=(?:SUM|AVERAGE|MIN|MAX|COUNT)\({CELL}(?::{CELL})?\)")
bridge = None


def required_text(value, limit):
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise ValueError("Provide nonempty text within the tool's size limit.")
    return value


def calc_range(model, args):
    sheet = model.Sheets.getByName(required_text(args.get("sheet"), 128))
    address = required_text(args.get("range"), 32).upper()
    if not RANGE.fullmatch(address):
        raise ValueError("Use a local A1 cell or rectangular range such as A1:C5.")
    cells = sheet.getCellRangeByName(address)
    bounds = cells.getRangeAddress()
    width = bounds.EndColumn - bounds.StartColumn + 1
    height = bounds.EndRow - bounds.StartRow + 1
    if width * height > 500:
        raise ValueError("Use a range of up to 500 cells.")
    return sheet, cells, width, height


def literal(value):
    if isinstance(value, str):
        return len(value) <= 4096 and "\x00" not in value
    return type(value) in (int, float) and abs(value) <= 1e300 and math.isfinite(value)


def undoable(model, action):
    manager = model.getUndoManager()
    if manager.isLocked():
        raise ValueError("Undo is unavailable. Try after the current document action finishes.")
    manager.enterUndoContext("Norvi document edit")
    try:
        action()
    finally:
        manager.leaveUndoContext()


def editable_cells(sheet, cells, width, height):
    targets = tuple(tuple(cells.getCellByPosition(x, y) for x in range(width)) for y in range(height))
    for row in targets:
        for cell in row:
            address = cell.getRangeAddress()
            cursor = sheet.createCursorByRange(cell)
            cursor.collapseToCurrentArray()
            cursor.collapseToMergedArea()
            if cursor.getRangeAddress() != address:
                raise ValueError("Select ordinary cells outside merged cells and array formulas.")
    return targets


def write_literals(model, targets, values):
    manager = model.getUndoManager()
    changed = False

    def edit():
        nonlocal changed
        for row, data in zip(targets, values):
            for cell, value in zip(row, data):
                before = (cell.getType().value, cell.getFormula())
                if isinstance(value, str):
                    cell.setString(value)
                    matches = cell.getString() == value and cell.getType().value in ("EMPTY", "TEXT")
                else:
                    cell.setValue(float(value))
                    matches = cell.getValue() == value and cell.getType().value == "VALUE"
                changed = changed or (cell.getType().value, cell.getFormula()) != before
                if not matches:
                    raise ValueError("Calc rejected an edit to this range.")

    try:
        undoable(model, edit)
    except Exception:
        if changed:
            manager.undo()
        raise
    return changed


def writer_replace(model, args):
    old = required_text(args.get("old"), 4096)
    new = args.get("new")
    if not isinstance(new, str) or len(new) > 4096 or any(c in old + new for c in "\r\n\x00"):
        raise ValueError("Replace a single paragraph fragment at a time.")
    search = model.createSearchDescriptor()
    search.SearchString = old
    search.SearchCaseSensitive = True
    match = model.findFirst(search)
    if (match is None or match.String != old or match.Text != model.Text or
            model.findNext(match.End, search) is not None):
        raise ValueError("The exact text must occur once in the main document body.")
    # findNext starts after the match. Detect a second, overlapping occurrence too.
    cursor = model.Text.createTextCursorByRange(match.Start)
    cursor.goRight(1, False)
    following = model.findNext(cursor.Start, search)
    if following is not None:
        raise ValueError("The exact text must occur once in the main document body.")
    undoable(model, lambda: setattr(match, "String", new))
    return {"changed": old != new}


@dataclass
class Grant:
    model: object
    kind: str
    title: str
    url: str
    key: str
    expiry: float


class Call(unohelper.Base, XCallback):
    def __init__(self, callback):
        self.callback = callback
        self.lock = Lock()
        self.done = Event()
        self.cancelled = False
        self.result = None

    def notify(self, _):
        with self.lock:
            if self.cancelled:
                return
            try:
                self.result = {"result": self.callback()}
            except ValueError as error:
                self.result = {"error": str(error)}
            except Exception:
                self.result = {"error": "LibreOffice could not complete this request."}
            finally:
                self.done.set()


class Bridge:
    def __init__(self, context):
        self.callback = context.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", context)
        self.grant = None
        runtime = Path(os.environ["XDG_RUNTIME_DIR"])
        info = runtime.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("A private Linux runtime directory is required.")
        self.path = runtime / "norvi-office.sock"
        self.lock_fd = os.open(runtime / "norvi-document-tools.lock",
                               os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                info = self.path.lstat()
            except FileNotFoundError:
                pass
            else:
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError("The document bridge socket path is in use.")
                self.path.unlink()
            self.socket.bind(str(self.path))
            self.path.chmod(0o600)
            self.socket.listen(4)
        except BaseException:
            self.socket.close()
            os.close(self.lock_fd)
            raise
        Thread(target=self.serve, name="norvi-office-bridge", daemon=True).start()

    def serve(self):
        while True:
            peer, _ = self.socket.accept()
            with peer:
                try:
                    peer.settimeout(2)
                    _, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        continue
                    with peer.makefile("rb") as stream:
                        line = stream.readline(REQUEST_LIMIT + 1)
                    if not line.endswith(b"\n") or len(line) > REQUEST_LIMIT:
                        continue
                    request = json.loads(line)
                    call = Call(lambda: self.handle(request))
                    self.callback.addCallback(call, None)
                    if not call.done.wait(3):
                        # Cancel queued requests. If already running, return its result.
                        with call.lock:
                            call.cancelled = True
                    result = call.result or {"error": "LibreOffice is busy. Try again."}
                    peer.sendall(json.dumps(result).encode() + b"\n")
                except (OSError, UnicodeError, ValueError):
                    continue

    def handle(self, request):
        grant = self.grant
        if grant is None or monotonic() >= grant.expiry:
            self.grant = None
            raise ValueError("Share an open document from LibreOffice first.")
        model = grant.model
        try:
            active = model.getCurrentController() is not None and model.getURL() == grant.url
        except Exception:
            active = False
        if not active:
            self.grant = None
            raise ValueError("The shared document closed or changed location. Share it again.")
        if not isinstance(request, dict):
            raise ValueError("Invalid document request.")
        operation = request.get("operation")
        if operation == "describe":
            details = {"document": grant.key, "kind": grant.kind,
                       "title": grant.title, "read_only": model.isReadonly()}
            if grant.kind == "calc":
                details["sheets"] = list(model.Sheets.getElementNames())[:100]
            return details
        if request.get("document") != grant.key:
            raise ValueError("The shared document changed. Run document_info again.")
        if grant.kind == "writer" and operation == "writer_read":
            cursor = model.Text.createTextCursor()
            cursor.gotoStart(False)
            offset = request.get("offset", 0)
            if type(offset) is not int or not 0 <= offset <= 30000:
                raise ValueError("Use an offset between 0 and 30,000.")
            if offset and not cursor.goRight(offset, False):
                return {"text": "", "end": True}
            more = cursor.goRight(4000, True)
            return {"text": cursor.String, "end": not more}
        if grant.kind == "writer" and operation == "writer_replace":
            if model.isReadonly():
                raise ValueError("The document is read-only.")
            return writer_replace(model, request)
        if grant.kind == "calc" and operation in ("calc_read", "calc_write"):
            sheet, cells, width, height = calc_range(model, request)
            current = cells.getFormulaArray()
            types = [[cells.getCellByPosition(x, y).getType().value for x in range(width)] for y in range(height)]
            snapshot = (grant.key, sheet.Name, request["range"].upper(), current, types)
            revision = sha256(json.dumps(snapshot, ensure_ascii=False).encode()).hexdigest()
            if operation == "calc_read":
                if sum(len(value) for row in current for value in row) > 30000:
                    raise ValueError("The range contains too much text. Read a smaller range.")
                return {"values": cells.getDataArray(), "formulas": current, "revision": revision}
            if model.isReadonly() or sheet.isProtected():
                raise ValueError("The sheet is protected or read-only.")
            if request.get("expected") != revision:
                raise ValueError("Cells changed since the read or the range differs. Read the range again.")
            formula = request.get("formula")
            values = request.get("values")
            if formula is not None:
                if values is not None or (width, height) != (1, 1) or not FORMULA.fullmatch(
                        required_text(formula, 128).upper()):
                    raise ValueError("Use a single-cell SUM, AVERAGE, MIN, MAX or COUNT over a local range.")
                cell = editable_cells(sheet, cells, width, height)[0][0]
                undoable(model, lambda: cell.setFormula(formula.upper()))
            else:
                if (not isinstance(values, list) or len(values) != height or
                        any(not isinstance(row, list) or len(row) != width or
                            not all(literal(value) for value in row) for row in values)):
                    raise ValueError("Supply a rectangular array of text and numbers matching the range.")
                return {"changed": write_literals(model, editable_cells(sheet, cells, width, height), values)}
            return {"changed": True}
        raise ValueError("That operation is unavailable for the shared document.")


class Handler(unohelper.Base, XInitialization, XDispatchProvider, XDispatch):
    def __init__(self, context):
        self.context = context
        self.frame = None

    def initialize(self, arguments):
        self.frame = arguments[0]

    def queryDispatch(self, url, target, flags):
        return self if self.frame and url.Complete in (START, STOP) else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def addStatusListener(self, listener, url):
        pass

    def removeStatusListener(self, listener, url):
        pass

    def message(self, text, confirm=False):
        window = self.frame.getContainerWindow()
        buttons = BUTTONS_YES_NO | DEFAULT_BUTTON_NO if confirm else BUTTONS_OK
        box = window.getToolkit().createMessageBox(
            window, QUERYBOX if confirm else INFOBOX, buttons, "Norvi Document Tools", text,
        )
        try:
            return box.execute()
        finally:
            box.dispose()

    def dispatch(self, url, arguments):
        global bridge
        if url.Complete == STOP:
            if bridge:
                bridge.grant = None
            self.message("Document sharing stopped.")
            return
        if url.Complete != START:
            return
        model = self.frame.getController().getModel()
        kind = "calc" if model.supportsService(CALC) else "writer" if model.supportsService(WRITER) else None
        if not kind:
            return
        if self.message(
            "Share this document with local tools running under your Linux account for 30 minutes? "
            "Connected AI sessions may send excerpts to their configured provider. "
            "You can stop sharing from the LibreOffice menu.", confirm=True,
        ) != YES:
            return
        try:
            if bridge is None:
                bridge = Bridge(self.context)
            bridge.grant = Grant(model, kind, self.frame.getTitle()[:200], model.getURL(),
                                 secrets.token_hex(16), monotonic() + TIME_LIMIT)
        except (OSError, KeyError, ValueError):
            self.message("Could not start the private document bridge. Check for another LibreOffice session.")


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Handler, IMPLEMENTATION, ("com.sun.star.frame.ProtocolHandler",))
