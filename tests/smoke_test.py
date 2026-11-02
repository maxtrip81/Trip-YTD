"""Prova di Trip YTD installato, usata da GitHub Actions.

Uso: python smoke_test.py <mac|windows|linux>, con il server di Trip YTD già avviato.
Controlla il server, installa i componenti, prova un download breve e chiude Trip YTD.
YouTube rifiuta spesso i download dai server cloud: in quel caso è solo un avviso.
"""

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:47320/"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(path, body=None):
    req = urllib.request.Request(
        BASE + path, data=None if body is None else json.dumps(body).encode(),
        headers={"X-Trip-YTD": "1", "Content-Type": "application/json"},
        method="GET" if body is None else "POST")
    with OPENER.open(req, timeout=30) as r:
        return json.load(r)


def wait(check, timeout, what):
    end = time.time() + timeout
    while time.time() < end:
        try:
            result = check()
            if result:
                return result
        except OSError:
            pass
        time.sleep(2)
    sys.exit("Tempo scaduto: " + what)


def main():
    platform = sys.argv[1]
    print("server:", wait(lambda: call("api/ping"), 90, "avvio del server"))
    state = call("api/state")
    if state["platform"] != platform:
        sys.exit("piattaforma %r invece di %r" % (state["platform"], platform))

    call("api/setup", {})

    def setup_done():
        s = call("api/state")["setup"]
        if s["error"]:
            sys.exit("Installazione dei componenti non riuscita: " + s["error"])
        return s["installed"] and not s["running"] and s

    setup = wait(setup_done, 900, "installazione dei componenti")
    print("componenti:", ", ".join(c["label"] for c in setup["components"]),
          "| motore:", call("api/state")["engine"]["version"])

    job = call("api/jobs", {"url": "https://youtu.be/jNQXAC9IVRw", "format": "mp3"})

    def job_done():
        j = next(j for j in call("api/state")["jobs"] if j["id"] == job["id"])
        return j["status"] in ("done", "error") and j

    j = wait(job_done, 300, "download di prova")
    if j["status"] == "done":
        print("download di prova riuscito: %s (%d byte)" % (j["filename"], j["size"]))
    else:
        print("::warning::Download di prova non riuscito (YouTube blocca spesso i server cloud): %s %s"
              % (j["error"], j["detail"]))

    call("api/quit", {})
    print("ok")


if __name__ == "__main__":
    main()
