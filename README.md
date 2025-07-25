# glowing-octo-winner
An automated system to plan an agroforestry system.

# Start up
[python virtual enviroments](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#create-and-use-virtual-environments)

```bash
pip install -r requirements.txt

export BRAVE_VERSION="{brave://version/}"

export BRAVE_BINARY_PATH="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
```

# Run project
```python
python -m src.services.local_data_importer
```

# Documentation 
docs/                 # All project documentation
├── architecture/
│   ├── system_context.md
│   ├── container_diagram.plantuml
│   └── core_functionality_sequence.plantuml
└── project_timeline.md