#!/usr/bin/env python3
from __future__ import annotations

import socket
import threading
from contextlib import closing
from time import sleep

from werkzeug.serving import make_server

from app_runtime import configure_runtime_environment


configure_runtime_environment()

from ui_app import app


def find_free_port(host: str = "127.0.0.1") -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((host, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


class ServerThread(threading.Thread):
    def __init__(self, flask_app, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self._server = make_server(host, port, flask_app, threaded=True)
        self._context = flask_app.app_context()
        self._context.push()

    def run(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._context.pop()


def main() -> int:
    try:
        import webview
    except ImportError:
        raise SystemExit(
            "pywebview non installato. Installa le dipendenze aggiornate o esegui il launcher dal progetto."
        )

    host = "127.0.0.1"
    port = find_free_port(host)
    server = ServerThread(app, host, port)
    server.start()

    window = webview.create_window(
        title="Trascrizione Locale",
        url=f"http://{host}:{port}",
        width=1280,
        height=920,
        min_size=(1000, 720),
        text_select=True,
    )

    def focus_window() -> None:
        try:
            import AppKit  # type: ignore

            sleep(0.4)
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            window.show()
            window.restore()
        except Exception:
            pass

    try:
        webview.start(func=focus_window, gui="cocoa", debug=False)
    finally:
        server.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
