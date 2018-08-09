import json

with open("paragraphs.json", "r") as f:
    data = json.loads(f.read())
    keys = sorted(list(map(int, data.keys())))
    for k in keys:
        print(k, " => ", len(data[str(k)]))
