FROM python:3.10-slim

ADD main.py ./app/
COPY ./requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade -r /app/requirements.txt

ENTRYPOINT ["python"]
CMD ["./app/main.py"]