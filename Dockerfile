FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md* ./
COPY pcc ./pcc
RUN pip install --no-cache-dir ".[api]"
RUN useradd --system --create-home --uid 10001 pcc \
    && mkdir -p /data && chown pcc:pcc /data
ENV PCC_CONFIG_DIR=/data
VOLUME /data
EXPOSE 8765
USER pcc
CMD ["pcc","serve","--host","0.0.0.0","--port","8765"]
