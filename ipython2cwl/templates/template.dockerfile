FROM {python_version}
COPY . /app
RUN cd /app && pip install -r requirements.txt && python setup.py install
