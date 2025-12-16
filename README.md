# cli user lookup

## setup

```bash
git clone https://github.com/azuda/run_lookup.git
cd run_lookup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "alias lookup=\"$PWD/.venv/bin/python3 $PWD/lookup.py\"" >> ~/.zshrc
source ~/.zshrc
```

## usage

```bash
lookup -h
```
