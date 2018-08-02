import re

with open("essays.json", "r") as content_file:
    text = content_file.read()
    text = re.sub(r'}.?\].*\[.?{', '},{', text, flags=re.DOTALL)
    print(text)
