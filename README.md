# cli user lookup

## setup


### dependencies
```bash
git clone https://github.com/azuda/run_lookup.git
cd run_lookup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
gpg --output .env --decrypt .env.gpg
```

### alias

```bash
echo "alias lookup=\"$PWD/.venv/bin/python3 $PWD/lookup.py\"" >> ~/.zshrc
source ~/.zshrc
```

## usage

```bash
lookup -h
```

### pagination details
The Veracross API responses don't include a `total_pages` field. The script therefore continues requesting pages until an empty page is returned. If you need to cap the number of pages fetched (for development or to avoid runaway requests) set the `MAX_PAGES` environment variable to a positive integer. For example:

```bash
export MAX_PAGES=10   # fetch at most 10 pages
lookup
```
