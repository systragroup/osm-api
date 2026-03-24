## Quetzal OSM-api

Scripts to fetch and simplify OSM network.
1) remove cul-de-sac
2) split links to oneways
3) simplify links (removing deg 2 nodes)
4) process list in columns
5) add elevation and slopes


## Deploy



## Unit Tests

```bash
python tests/run_tests.py
``` 
for coverage report:

```bash
pip install coverage
``` 
```bash
coverage run -m unittest discover
```
```bash
coverage report
```
for a nicer report:
```bash
coverage html
```

