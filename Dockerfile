FROM public.ecr.aws/lambda/python:3.8.2023.05.29.18
COPY ./requirements.txt ./requirements.txt
RUN pip install -r ./requirements.txt

COPY ./ ./
CMD ["main.handler"]
