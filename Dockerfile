FROM python:3.11-slim

ARG TARGETARCH
ARG TERRAFORM_VERSION=1.8.5

# Create non-root user
RUN apt-get update \
	&& apt-get install -y --no-install-recommends ca-certificates curl unzip \
	&& arch="${TARGETARCH:-amd64}" \
	&& curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${arch}.zip" -o /tmp/terraform.zip \
	&& unzip /tmp/terraform.zip -d /usr/local/bin \
	&& chmod 0755 /usr/local/bin/terraform \
	&& rm -f /tmp/terraform.zip \
	&& apt-get purge -y --auto-remove curl unzip \
	&& rm -rf /var/lib/apt/lists/* \
	&& useradd -m appuser
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
	&& rm -rf /root/.cache

COPY . .

# Change ownership and permissions
RUN mkdir -p /data \
	&& chown -R appuser:appuser /app /data
USER appuser

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
