
Add license from root:
addlicense -f .private/header.txt -v .

Add attributions:
go-licenses report ./... --template=../.private/license.tmpl --ignore=spored > ../ATTRIBUTIONS.md
