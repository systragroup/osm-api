## Quetzal OSM-api

Scripts to fetch and simplify OSM network


## Deploy

1) See instruction on AWS ECR to deploy Docker image
2) Update Lambda function image

## Unit Tests

```bash
python test/test.py
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
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d "{\"overpassQuery\":\"[out:json][timeout:180];\\n      (\\n      way[\\\"highway\\\"=\\\"motorway\\\"](45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215);\\nway[\\\"highway\\\"=\\\"motorway_link\\\"](45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215);\\nway[\\\"highway\\\"=\\\"trunk\\\"](45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215);\\nway[\\\"highway\\\"=\\\"trunk_link\\\"](45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215);\\nway[\\\"highway\\\"=\\\"primary\\\"](45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215);\\nway[\\\"highway\\\"=\\\"primary_link\\\"](45.436521914253944,-73.79789929568945,45.59889118488431,-73.46685884481215);\\n);\\n      out body;\\n      >;\\n      out skel qt;\\n      \",\"tags\":[\"highway\",\"maxspeed\",\"lanes\",\"name\",\"oneway\",\"surface\"],\"callID\":\"test\",\"elevation\":true}"
```




CallId correspond to a folder on the s3 Bucket.
