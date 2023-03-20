FROM public.ecr.aws/lambda/python:3.8.2023.01.11.07
COPY ./requirements.txt ./requirements.txt
RUN pip install -r ./requirements.txt

COPY ./ ./
CMD ["main.handler"]