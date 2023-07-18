## Quetzal OSM-api

Scripts to fetch and simplify OSM network.
1) remove cul-de-sac
2) split links to oneways
3) simplify links (removing deg 2 nodes)
4) process list in columns
5) add elevation and slopes


## Deploy

1) See instruction on AWS ECR to deploy Docker image
2) Update Lambda function image

## Unit Tests

```bash
python tests/run_tests.py
``` 

## TEST Lambda function

1) create a test.env file at the root of this folder (with the DockerFile)
```bash
AWS_ACCESS_KEY_ID=[your access key]
AWS_SECRET_ACCESS_KEY=[your secret key]
AWS_REGION=ca-central
BUCKET_NAME=quenedi-osm
AWS_LAMBDA_FUNCTION_MEMORY_SIZE=3000
```
2) Build the Docker
```bash
docker build -t osm-api:latest .

```
3) Run the docker with the environment variable
```bash
docker run -p 9000:8080 --env-file 'test.env' osm-api 
```
4) from another terminal window:
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d "{\"bbox\":[45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215],\"highway\":[\"motorway\",\"motorway_link\",\"trunk\",\"trunk_link\",\"primary\",\"primary_link\",\"secondary\",\"secondary_link\",\"cycleway\"],\"callID\":\"test\",\"elevation\":true}"
```


CallId correspond to a folder on the s3 Bucket.
