import re
import json

with open("essays.json", "r") as content_file:
    text = content_file.read()
    text = re.sub(r'}.?\].*\[.?{', '},{', text, flags=re.DOTALL)
    data = json.loads(text)

    filtered_data = []
    for item in data:
        if (item["type"] == "essay" and len(item["text"]) > 0) or item["type"] == "prompt":
            filtered_data.append(item)

    print("Total essays: ", len(filtered_data))

    with open("essays_fixed.json", "w") as out_file:
       out_file.write(json.dumps(filtered_data))
