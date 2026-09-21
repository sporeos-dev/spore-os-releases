#!/usr/bin/env python3

from ensure_spdx import ensure_spdx
from finesse_go import finesse_go
from update_attributions import update_attributions
from update_preamble_and_footer import update_preamble_and_footer

def main() -> None:
	ensure_spdx()
	finesse_go()
	update_attributions()
	update_preamble_and_footer()

if __name__ == "__main__":
	main()
