# Fix jpeg metadata for correct import in Photos

```
Fixing old picture timestamps for correct import in Photos
usage: run.py [-h] [-v] [--date-map DATE_MAP]
              [--picture-database PICTURE_DATABASE] -d DIR [--force]
              command ...

positional arguments:
  command
    list                List the Picure Database
    issues              list the problematic files in the Picture Database
    remove              remove file(s) from Picture Database
    create              create data map
    scan                create picture database
    map                 map directory date db over file
    info                get exif info
    fix                 run fixes
    update              update manual fixes from a issues csv
    write               write fixed metadata to files

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         debug output
  --date-map DATE_MAP   dir date map
  --picture-database PICTURE_DATABASE
                        picture db file
  -d DIR, --dir DIR     process entire dir
  --force               force file overwrite
```

```
usage: run.py list [-h] [-o OUT] [--filter FILTER]

optional arguments:
  -h, --help         show this help message and exit
  -o OUT, --out OUT  output to csv
  --filter FILTER    filter output with field=value,field2=value2,...
usage: run.py issues [-h] [-o OUT] [--filter FILTER]

optional arguments:
  -h, --help         show this help message and exit
  -o OUT, --out OUT  output to csv
  --filter FILTER    filter output with field=value,field2=value2,...
```

```
usage: run.py remove [-h] -n NAME

optional arguments:
  -h, --help            show this help message and exit
  -n NAME, --name NAME  filename
```

```
usage: run.py create [-h]

optional arguments:
  -h, --help  show this help message and exit
```

```
usage: run.py scan [-h]

optional arguments:
  -h, --help  show this help message and exit
```

```
usage: run.py map [-h]

optional arguments:
  -h, --help  show this help message and exit
```

```
usage: run.py info [-h] -f FILE

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  filename
```

```
usage: run.py fix [-h]

optional arguments:
  -h, --help  show this help message and exit
```

```
usage: run.py update [-h] -i INPUT [--force]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        input issues.csv
  --force               force update
```

```
usage: run.py write [-h] [--force]

optional arguments:
  -h, --help  show this help message and exit
  --force     force update
```
