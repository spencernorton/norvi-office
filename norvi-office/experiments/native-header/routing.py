"""Exact window routing for the isolated native-header action broker."""

COMMANDS = {
    "open": ".uno:Open",
    "save": ".uno:Save",
    "undo": ".uno:Undo",
    "redo": ".uno:Redo",
    "settings": ".uno:OptionsTreeDialog",
}


def uses_pipe(cmdline, pipe):
    return f"--accept=pipe,name={pipe};urp;".encode() in cmdline.split(b"\0")


def matching_frame(frames, handle):
    """Never fall back to the focused frame: another window may own focus."""
    if not isinstance(handle, int) or handle <= 0 or (handle & 0xFFFFFFFF) == 0:
        return None
    matches = []
    for frame in frames:
        try:
            peer = frame.getContainerWindow().getWindowHandle((), 6)
            # The published XWINDOW struct uses a signed 32-bit WindowHandle,
            # even when GTK/Wayland's native surface identity is pointer-sized.
            # Require a unique match; never resolve a collision by caption/focus.
            if peer is not None and (peer.WindowHandle & 0xFFFFFFFF) == (handle & 0xFFFFFFFF):
                matches.append(frame)
        except Exception:
            continue  # A frame can be disposed while another window is opening.
    return matches[0] if len(matches) == 1 else None
