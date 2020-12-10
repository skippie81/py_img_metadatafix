#!/usr/bin/env python3

import os,sys
import logging
import exif
import datetime
import argparse
import json,csv
import re

log = logging.getLogger('EXIF Modifier')
log.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fh = logging.FileHandler('exif.log')
fh.setFormatter(logging.INFO)
fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(fmt)
fh.setFormatter(fmt)
log.addHandler(ch)
log.addHandler(fh)


EXIF_DATETIME_FORMAT = '%Y:%m:%d %H:%M:%S'
IMAGE_EXTENTIONS = ['jpg','jpeg']

class DirData(object):
    @classmethod
    def scan(cls,dir,db_file):
        dirlist = {}
        filelist = []
        for root,dirs,files in os.walk(dir):
            log.debug('root: %s' % root)
            log.debug('dirs: %s' % dirs)
            log.debug('files: %s' % files)
            for file in files:
                filelist.append(os.path.join(root,file))

        for file in filelist:
            dirkey = os.path.dirname(file.replace(args.dir,''))
            if dirkey not in dirlist.keys():
                data = FotoData.process_file(file)
                if data['ok']:
                    log.debug('found dir %s with date %s' % (dirkey,data['exif']['datetime']) )
                    dirlist[dirkey] = data['exif']['datetime']

        return DirData(data,db_file)

    @classmethod
    def load(cls,db_file):
        try:
            with open(db_file,'r') as f:
                db = json.load(f)
                f.close()
        except Exception as e:
            raise e
        return DirData(db,db_file)

    def __init__(self,db,db_file='dirlist.json'):
        self.db = db
        self.db_file = db_file

    def safe(self):
        with open(self.db_file,'w') as db_file:
            json.dump(self.db,db_file,indent=4)
            db_file.close()

    def get(self,dirkey):
        try:
            return self.db[dirkey]
        except KeyError:
            return None

class FotoData(object):

    CSV_FIELDNAMES = ['filename','has_exif','datetime','datetime_original','datetime_digitized','ok','issue','can_fix']

    @classmethod
    def get_exif_from_file(cls,filename):
        with open(filename,'rb') as imagefile:
            try:
                img = exif.Image(imagefile)
            except Exception as e:
                imagefile.close()
                raise e
            log.debug('has exif: %s' % img.has_exif)
            imagefile.close()
        return img

    @classmethod
    def process_file(cls,filename):
        log.info('Processing file %s' % filename)
        if os.path.basename(filename).split('.').pop().lower() not in IMAGE_EXTENTIONS:
            return {'filename': filename,'ok': False, 'issue': 'NO PICTURE FILE'}
        try:
            img = get_exif_from_file(filename)
        except Exception as e:
            return {'filename': filename,'ok': False,'issue': '%s' % e}
        data = {
            'filename': filename,
            'exif': {},
            'has_exif': img.has_exif,
            'ok': False
        }

        if img.has_exif:
            try:
                data['exif']['datetime'] = img.datetime
                data['ok'] = True
            except AttributeError:
                data['issue'] = 'NO DATETIME IN EXIF'
                return data
            try:
                data['exif']['datetime_original'] = img.datetime_original
            except AttributeError:
                data['exif']['datetime_original'] = img.datetime
            try:
                data['exif']['datetime_digitized'] = img.datetime_digitized
            except AttributeError:
                date['exif']['datetime_digitized'] = img.datetime
        else:
            data['issue'] = 'NO METADATA'
        return data

    @classmethod
    def scan(cls,path,db_file='db.json'):
        filelist = []
        for root,dirs,files in os.walk(dir):
            for file in files:
                filelist.append(os.path.join(root,file))
        fotodata = []
        for f in filelist:
            fotodata.append(FotoData.process_file(file))
        db = {}
        for f in fotodata:
            db[f['filename']] = f
        return FotoData(path,db,db_file=db_file)

    @classmethod
    def load(cls,path,db_file):
        try:
            log.debug('loading fotodb from %s' % db_file)
            with open(db_file,'r') as f:
                db = json.load(f)
                f.close()
        except Exception as e:
            raise e

        need_safe = False
        if type(db) == type([]):
            log.debug('db file is flat file list ... converting ... ')
            new_db = {}
            for f in db:
                new_db[f['filename']] = f
            db = new_db
            need_safe = True

        r = re.compile('^%s' % os.path.join(path,''))
        for f in list(db.keys()):
            if r.match(f):
                log.debug('found basepath in %s' % f)
                k = r.sub('',f)
                log.debug('%s new key is %s' % (f,k))
                i = db.pop(f)
                i['filename'] = r.sub('',i['filename'])
                db[k] = i
                need_safe = True

        fd = FotoData(path,db,db_file=db_file)
        if need_safe:
            log.debug('Saving updated db on load')
            fd.safe()
        return fd

    def __init__(self,path,db,db_file='db.json'):
        self.path = path
        self.db = db
        self.db_file = db_file

    def safe(self):
        log.debug('saving %s' % self.db_file)
        with open(self.db_file,'w') as f:
            json.dump(self.db,f,indent=4)
            f.close()

    def remove(self,name):
        for k in list(self.db.keys()):
            if os.path.basename(k) == name:
                self.db.pop(k)

    def problems(self):
        db = {}
        for k in self.db.keys():
            if not self.db[k]['ok']:
                db[k] = self.db[k]
        return FotoData(self.path,db,'%s.problems' % self.db_file)

    def dir_date_map(self,date_db):
        for k in self.db.keys():
            if not self.db[k]['ok'] and self.db[k]['issue'] in ['NO METADATA','NO DATETIME IN EXIF']:
                dirkey = os.path.dirname(k)
                log.debug('looking for %s in date map' % dirkey)
                date = date_db.get(dirkey)
                if date != None:
                    log.info('Updating picutre file %s metata to same as dir data %s' % (k,date))
                    self.db[k]['exif'] = { 'datetime': date, 'datetime_original': date, 'datetime_digitized': date }
                    self.db[k]['issue'] = 'METADATA MATCHED TO FILES IN SAME DIR'
                else:
                    log.debug('%s not found in dirmap' % dirkey)
                    dirkey = os.path.dirname(dirkey)
                    while dirkey != '':
                        log.debug('trying key %s' % dirkey)
                        date = date_db.get(dirkey)
                        if date != None:
                            log.info('Updating picture file %s metadata to same as higher level dir %s date is %s' % (k,dirkey,date))
                            self.db[k]['exif'] = { 'datetime': date, 'datetime_original': date, 'datetime_digitized': date }
                            self.db[k]['issue'] = 'METADATA MATCHED TO FILE IN HIGHER DIR %s' % dirkey
                            break
                        dirkey = os.path.dirname(dirkey)

    def fix(self):
        r = re.compile('IMG-([0-9]{4})([0-9]{2})([0-9]{2})-WA.*\.jpg$')
        for k in self.db.keys():
            if not self.db[k]['ok']:
                if self.db[k]['issue'] == 'NO DATETIME IN EXIF':
                    log.debug('checking %s for other metadata' % k)
                    img = FotoData.get_exif_from_file(os.path.join(self.path,k))
                    log.debug('%s' % dir(img))
                    issue = 'DATETIME FOUND IN OTHER METADATA'
                    try:
                        date = img.datetime_original
                    except AttributeError:
                        try:
                            date = img.datetime_digitized
                        except AttributeError:
                            log.debug('regex matching for date in file name %s' % k)
                            if r.match(os.path.basename(k)):
                                log.debug('regex matched')
                                groups = r.match(os.path.basename(k)).groups()
                                date = '%s:%s:%s 12:00:00' % (groups[0],groups[1],groups[2])
                                log.debug('date out of regex is %s' % date)
                                issue = 'DATETIME FOUND IN FILENAME'
                            else:
                                continue
                    log.info('updating %s datetime to %s' % (k,date))
                    self.db[k]['exif'] = {'datetime': date, 'datetime_original': date, 'datetime_digitized': date}
                    self.db[k]['issue'] = issue
                elif self.db[k]['issue'] == 'NO METADATA':
                    log.debug('no metadata, matching file %s for regex' % k)
                    if r.match(os.path.basename(k)):
                        log.debug('regex matched')
                        groups = r.match(os.path.basename(k)).groups()
                        date = '%s:%s:%s 12:00:00' % (groups[0],groups[1],groups[2])
                        log.debug('date out of regex is %s' % date)
                        issue = 'DATETIME FOUND IN FILENAME'
                        self.db[k]['exif'] = {'datetime': date, 'datetime_original': date, 'datetime_digitized': date}
                        self.db[k]['issue'] = issue

    def csvwrite(self,filename,**kwargs):
        with open(filename,'w') as csvfile:
            csvwriter = csv.DictWriter(csvfile,fieldnames=self.CSV_FIELDNAMES)
            csvwriter.writeheader()
            for i in self:
                i['can_fix'] = None
                if not i['ok']:
                    if i['issue'] not in ['NO PICTURE FILE','NO METADATA','NO DATETIME IN EXIF']:
                        i['can_fix'] = True
                    else:
                        i['can_fix'] = False

                do_write = True
                for key in kwargs:
                    match = True
                    skey = key
                    if key.endswith('!'):
                        match = False
                        skey = key.replace('!','')

                    try:
                        if type(i[skey]) == type(True):
                            if kwargs[key].lower() in ['y','yes','true']:
                                value = True
                            else:
                                value = False
                        else:
                            if kwargs[key].lower() in ['null','none']:
                                value = None
                            else:
                                value = kwargs[key]

                        if match and i[skey] != value:
                            do_write = False
                        if not match and i[skey] == value:
                            do_write = False
                    except KeyError as e:
                        log.error('no key %s' % e)
                        sys.exit(1)

                if do_write:
                    csvwriter.writerow(i)

            csvfile.close()

    def update_from_file(self,filename,field='issue',value='MANUAL FIX',force=False):
        with open(filename,'r') as csvfile:
            reader = csv.DictReader(csvfile,fieldnames=self.CSV_FIELDNAMES)
            for i in reader:
                if i[field] == value:
                    f = i['filename']
                    log.debug('Item markt for manual update: %s' % f)
                    try:
                        try:
                            if not self.db[f]['ok']:
                                log.debug('entry in db selected for manual update as no automatic fix could be found')

                                if 'exif' not in self.db[f].keys():
                                    log.debug('no exif for db entry yet creating')
                                    self.db[f]['exif'] = {'datetime': None, 'datetime_original': None, 'datetime_digitized': None}
                                elif 'datetime' not in self.db[f]['exif'].keys():
                                    log.debug('no datetime key in current exif creating')
                                    self.db[f]['exif'] = {'datetime': None, 'datetime_original': None, 'datetime_digitized': None}
                                else:
                                    log.debug('current exif: %s' % self.db[f]['exif'])

                                if self.db[f]['exif']['datetime'] == None or force:
                                    log.debug('loading datetime for manual update file')
                                    date = i['datetime']
                                    log.debug('found %s' % date)
                                    if i['datetime_original'] != None and i['datetime_original'] != '':
                                        date_original = i['datetime_original']
                                    else:
                                        date_original = date
                                    if i['datetime_digitized'] != None and i['datetime_digitized'] != '':
                                        date_digitized = i['datetime_digitized']
                                    else:
                                        date_digitized = date
                                    log.info('updating %s to datetime %s' % (f,date))
                                    try:
                                        self.db[f]['exif']['datetime'] = date
                                        self.db[f]['exif']['datetime_original'] = date_original
                                        self.db[f]['exif']['datetime_digitized'] = date_digitized
                                        self.db[f]['issue'] = 'MANUAL FIX'
                                        log.debug('update ok')
                                    except KeyError as e:
                                        log.debug('no exif with key %s' % e)
                                        sys.exit(1)
                                else:
                                    log.debug('there is data in exif')
                                    log.warning('not updating entry %s as there is alreada a date set %s. use --force to overwrite' % (f,self.db[f]['exif']['datetime']) )
                            else:
                                log.info('a fix was already done for %s use --force to overwrite' % f)
                        except KeyError as e:
                            log.error('something wend wrong: %s' % e)
                            sys.exit(1)
                    except KeyError as e:
                        log.warning('Entry %s not found in picture database' % f)

    def __str__(self):
        out = '%-40s%-6s%-20s%-6s%-30s\n' % ('FILENAME','EXIF','DATETIME','OK','ISSUE')
        out += '\n'
        for i in self:
            out += '%-40s%-6s%-20s%-6s%-30s\n' % (i['filename'],i['has_exif'],i['datetime'],i['ok'],i['issue'])
        return out

    def __iter__(self):
        self.keys = list(self.db.keys())
        return self

    def __next__(self):
        if len(self.keys) == 0:
            raise StopIteration

        i = self.db[self.keys.pop()]
        item = {
            'filename': i['filename'],
            'has_exif': False,
            'datetime': None,
            'datetime_original': None,
            'datetime_digitized': None,
            'ok': i['ok'],
            'issue': None
        }

        try:
            item['has_exif'] = i['has_exif']
            item['datetime'] = i['exif']['datetime']
            item['datetime_original'] = i['exif']['datetime_original']
            item['datetime_digitized'] = i['exif']['datetime_digitized']
        except KeyError:
            pass
        try:
            item['issue'] = i['issue']
        except KeyError:
            pass
        return item

class PictureUpdater(object):

    def __init__(self,db,dir='.'):
        self.db = db
        self.dir = dir

    def write_fixes(self,force=False):
        if not force:
            log.warning('not really writing files, use --force')
        for picture in self.db:
            if picture['datetime'] == None:
                log.debug('not touching %s as no datetime in db' % filename)
                continue
            filename = os.path.join(self.dir,picture['filename'])
            datetime = picture['datetime']
            log.debug('Updating %s' % filename)

            if os.path.isfile(filename):
                with open(filename,'rb') as f:
                    img = exif.Image(f)
                    f.close()
                log.debug('updating exif to date %s' % datetime)
                img.datetime = datetime
                img.datetime_original = datetime
                img.datetime_digitized = datetime
                if force:
                    log.info('writing file %s' % filename)
                    with open(filename,'wb') as new_file:
                        new_file.write(img.get_file())
                        new_file.close()
            else:
                log.warning('picture %s in db not on filesystem' % filename)

def get_parser(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('-v','--verbose',help='debug output',action='store_true')
    parser.add_argument('--date-map',help='dir date map',default='dirlist.json')
    parser.add_argument('--picture-database',help='picture db file',default='db.json')
    parser.add_argument('-d','--dir',help='process entire dir',required=True)
    parser.add_argument('--force',help='force file overwrite',action='store_true')

    command = parser.add_subparsers(dest='command',metavar='command',required=True)

    list = command.add_parser('list',help='List the Picure Database')
    list.add_argument('-o','--out',help='output to csv')
    list.add_argument('--filter',help='filter output with field=value,field2=value2,...')

    issues = command.add_parser('issues',help='list the problematic files in the Picture Database')
    issues.add_argument('-o','--out',help='output to csv')
    issues.add_argument('--filter',help='filter output with field=value,field2=value2,...')

    remove = command.add_parser('remove',help='remove file(s) from Picture Database')
    remove.add_argument('-n','--name',help='filename',required=True)

    create = command.add_parser('create',help='create data map')

    scan = command.add_parser('scan',help='create picture database')

    map = command.add_parser('map',help='map directory date db over file')

    info = command.add_parser('info',help='get exif info')
    info.add_argument('-f','--file',help='filename',required=True)

    fix = command.add_parser('fix',help='run fixes')

    update = command.add_parser('update',help='update manual fixes from a issues csv')
    update.add_argument('-i','--input',help='input issues.csv',required=True)
    update.add_argument('--force',help='force update',action='store_true')

    write = command.add_parser('write',help='write fixed metadata to files')
    write.add_argument('--force',help='force update',action='store_true')

    return parser.parse_args()

def main(args):
    args = get_parser(args)

    if args.verbose:
        log.setLevel(logging.DEBUG)
        log.debug('Debug logging enabled')

    if args.command == 'info':
        img = FotoData.get_exif_from_file(args.file)
        print(dir(img))
        sys.exit(0)

    filter = {}
    try:
        if args.filter != None:
            filter_list = args.filter.split(',')
            for i in filter_list:
                key = i.split('=')[0]
                value = ''.join(i.split('=')[1:])
                filter[key] = value
    except AttributeError:
        pass

    if args.command == 'create' and args.dir != None:
        log.info('Creating Directory Date map for %s' % args.dir)
        if os.path.isfile(args.date_map):
            log.warning('Date DB already exists')
            if not args.force:
                log.error('Not overwriting (use --force)')
                sys.exit(1)
            else:
                log.warning('Overwriting Date DB')
        dir_data = DirData.scan(args.dir,args.date_map)
        dir_data.safe()
    elif args.command == 'scan':
        if os.path.isfile(args.picture_database):
            log.warning('DB already exists')
            if not args.force:
                log.error('Not overwriting (use --force)')
                sys.exit(1)
            else:
                log.warning('Overwriting DB')
        log.info('Creating picture database for %s' % args.dir)
        foto_db = FotoData.scan(args.dir,args.picture_database)
        foto_db.safe()
    else:
        if not os.path.isfile(args.picture_database):
            log.error('No picture database %s found. Run scan first' % args.picture_database)
            sys.exit(1)
        if not os.path.isfile(args.date_map):
            log.error('No directory data map %s found. Run create first' % args.date_map)
            sys.exit(1)
        foto_db = FotoData.load(args.dir,args.picture_database)
        dir_db = DirData.load(args.date_map)

        if args.command == 'list':
            if args.out != None:
                foto_db.csvwrite(args.out,**filter)
            else:
                print('%s' % foto_db)
        if args.command == 'issues':
            p = foto_db.problems()
            if args.out == None:
                print('%s' % p)
            else:
                p.csvwrite(args.out,**filter)
        if args.command == 'remove':
            foto_db.remove(args.name)
            foto_db.safe()
        if args.command == 'map':
            foto_db.dir_date_map(dir_db)
            foto_db.safe()
        if args.command == 'fix':
            foto_db.fix()
            foto_db.safe()
        if args.command == 'update':
            foto_db.update_from_file(args.input,force=args.force)
            foto_db.safe()
        if args.command == 'write':
            problems = foto_db.problems()
            PictureUpdater(problems,dir=args.dir).write_fixes(force=args.force)

if '__main__' in __name__:
    log.info('START RUN')
    main(sys.argv[:1])
    log.info('STOP RUN')