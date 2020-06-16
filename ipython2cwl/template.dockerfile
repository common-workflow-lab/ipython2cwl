FROM python:{python_version}
COPY . /app
RUN pip install -r /app/requirements.txt
