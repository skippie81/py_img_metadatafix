# Fix jpeg metadata for correct import in Photos

Script to fix timestamp metadate of older picture to prepare for import in Photos

# Requirements

python3 and exif

```
pip3 install exif
```

# Usage

1. scan a directory full of pictures
```
    ./run.py -d <dir> scan
```
2. scan the direcory structure to create a date map for later use
```
    ./run.py -d <dir> create
```
3. optional: if the directory structure has some time structure you might try to match pictures whitout timestamp with oter pictures in same directory or higher level directory
```
    ./run.py -d <dir> map
```
4. run automatic fixes
```
    ./run.py -d <dir> fix
```
5. list pictures/files that might have a timestamp issue and output in a csv file
```
    ./run.py -d <dir> issues -o problems.csv
    ./run.py -d <dir> issues -o to_fix_manual.csv --filter can_fix=False,issue!="NO PICTURE FILE"
    ./run.py -d <dir> issues -o other_files.csv --filter issue="NO PICTURE FILE"
```
6. edit fix_manual.csv file
<br> open the csv file and input a timestamp in the datetime field for files and update the issue field to 'MANUAL FIX'
```
    ./run.py -d <dir> update -i to_fix_manual.csv
```
7. write new timestamps to image files
<br> use --force to really write the files. If not added it reads files applies fixes but does not save the image file
```
    ./run.py -d <dir> write --force
```

# Automatic fixes
* if no datetime field is found but there are other fields that provide a date use this timestamp
* try to find a date in the filename via a regex match YYYYMMDD in filename


# Help

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
```

```
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
usage: run.py info [-h] -f FILE

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  filename
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