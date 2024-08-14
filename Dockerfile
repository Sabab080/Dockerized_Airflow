FROM apache/airflow:2.9.1

USER root

# Install any OS-level dependencies here
RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential \
    default-libmysqlclient-dev


# Install Python dependencies
# COPY requirements.txt .

# RUN pip install --no-cache-dir -r requirements.txt

# Copy dags and scripts (if needed)
COPY dags /opt/airflow/dags
COPY plugins /opt/airflow/plugins
COPY sync_dags.sh /opt/airflow/sync_dags.sh


# Set environment variables (if needed)
ENV AIRFLOW__CORE__EXECUTOR=LocalExecutor
ENV AIRFLOW__CORE__FERNET_KEY=your_fernet_key
ENV AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow

# Default entrypoint
ENTRYPOINT ["tini", "--"]
CMD ["airflow", "webserver"]

