FROM python:3.12-slim-bookworm
COPY . /service
EXPOSE 8000
CMD ["python3", "/service/mcp_service.py", "--dir", "/service", "--port", "8000", "--name", "office"]
