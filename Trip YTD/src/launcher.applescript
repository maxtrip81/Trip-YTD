-- Avvia il server locale di Trip YTD e apre la pagina nel browser.
-- Il server si chiude da solo quando chiudi la pagina.
on run
	set serverScript to POSIX path of (path to resource "trip_ytd.py")
	do shell script "/usr/bin/python3 " & quoted form of serverScript & " > /dev/null 2>&1 &"
end run
