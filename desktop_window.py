#!/usr/bin/env python3
from __future__ import annotations

import socket
import shutil
import threading
from contextlib import closing
from pathlib import Path
from time import sleep

from werkzeug.serving import make_server

from app_runtime import configure_runtime_environment


configure_runtime_environment()

from ui_app import app, resolve_output_file


DISPLAY_APP_NAME = "Trascrivi!"


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


class DesktopApi:
    def __init__(self) -> None:
        self.window = None
        self.webview = None

    def attach(self, window, webview_module) -> None:
        self.window = window
        self.webview = webview_module

    def save_output_file(self, job_id: str, file_kind: str) -> dict:
        try:
            source_path = resolve_output_file(job_id, file_kind)
            if source_path is None:
                return {"ok": False, "error": "File di output non trovato."}

            if self.window is None or self.webview is None:
                return {"ok": False, "error": "Finestra desktop non disponibile."}

            selected = self.window.create_file_dialog(
                self.webview.SAVE_DIALOG,
                save_filename=source_path.name,
            )
            if not selected:
                return {"ok": False, "cancelled": True}

            if isinstance(selected, (list, tuple)):
                destination = Path(selected[0])
            else:
                destination = Path(str(selected))

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            return {"ok": True, "path": str(destination)}
        except Exception as exc:
            return {"ok": False, "error": f"Salvataggio non riuscito: {exc}"}


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
    api = DesktopApi()

    window = webview.create_window(
        title=DISPLAY_APP_NAME,
        url=f"http://{host}:{port}",
        width=1280,
        height=920,
        min_size=(1000, 720),
        text_select=True,
        js_api=api,
    )
    api.attach(window, webview)

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
