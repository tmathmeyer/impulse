# bootstrap makefile for building impulse

impulse:
	@zip -j /tmp/impulse.zip src/*.py
	@echo '#!/usr/bin/env python' | cat - /tmp/impulse.zip > impulse
	@chmod +x impulse
	@rm /tmp/impulse.zip