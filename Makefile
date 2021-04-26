COVERAGE_DIR=htmlcov

mypy:
	 mypy $$(find ipython2cwl -name '*.py')

coverage: coverage-run coverage-html coverage-pdf

coverage-run:
	coverage run --source ipython2cwl -m unittest discover tests

coverage-html:
	coverage html

coverage-pdf:
	wkhtmltopdf --title 'Coverage Report' --enable-local-file-access $(COVERAGE_DIR)/index.html $(COVERAGE_DIR)/ipython2cwl*.html $(COVERAGE_DIR)/ipython2cwl_coverage.pdf

clean:
	rm -rf $(COVERAGE_DIR)