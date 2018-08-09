echo "Fixing"
python fix.py
echo "Prettifying"
cat essays_fixed.json | python -m json.tool > essays_pretty.json
echo "Encoding"
echo -en "$(cat essays_pretty.json)" > essays_pretty_e.json
echo "Written to essays_pretty_e.json"
