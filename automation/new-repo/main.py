#!/usr/bin/env python3

from gather_info import gather_info
from setup_license import setup_license
from setup_preamble_and_footer import setup_preamble_and_footer

def main() -> None:
	setup = gather_info()
	setup_license(setup)
	setup_preamble_and_footer(setup)

if __name__ == "__main__":
	main()