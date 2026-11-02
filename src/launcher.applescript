-- Avvia il server locale di Trip YTD e apre la pagina nel browser.
-- Il server si chiude da solo quando chiudi la pagina.
on run
	set launcher to POSIX path of (path to resource "launch.sh")
	do shell script quoted form of launcher & " > /dev/null 2>&1 &"
end run
