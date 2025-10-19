roboauto: requirements
	pip install --break-system-packages .

requirements:
	pip install --break-system-packages -r requirements.txt

.PHONY: tags
tags:
	ctags -R --format=1 --languages=Python,PythonLoggingConfig
