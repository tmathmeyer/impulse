# bootstrap makefile for building impulse

impulse:
	@mkdir impulse
	@touch impulse/__init__.py
	@cp *.py impulse/
	@python3 -m impulse.impulse build :impulse
	@rm -rf impulse/
