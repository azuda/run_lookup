# cli user lookup

## setup

```bash
git clone repo_url
cd run_lookup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo alias lookup='/path/to/run_lookup/.venv/bin/python3 /path/to/run_lookup/lookup.py' >> ~/.zshrc
```

## usage

```bash
lookup -h
```
