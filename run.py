#!/usr/bin/env python3

import os
import sys
import signal
import logging
import exif
import datetime
import argparse
import json
import csv
import re
import math
import warnings

log = logging.getLogger('EXIF Modifier')
log.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fh = logging.FileHandler('exif.log')
fh.setLevel(logging.INFO)
fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(fmt)
fh.setFormatter(fmt)
log.addHandler(ch)
log.addHandler(fh)


EXIF_DATETIME_FORMAT = '%Y:%m:%d %H:%M:%S'
IMAGE_EXTENSIONS = ['jpg', 'jpeg']
IMG_FILENAME_REGEX = ".*-([0-9]{4})([0-9]{2})([0-9]{2})-.*"


class CleanExit(object):
    def __init__(self):
        signal.signal(signal.SIGINT, self.sigint_handler)
        self.exit = False

    def sigint_handler(self, signal_received, _):
        log.warning('CTRL-C pressed, exiting ...')
        log.debug('signal received %s' % signal_received)
        self.exit = True


class PrettyProgress(object):

    INCREASE = '.'
    ROTOR = ['\b|', '\b/', '\b-', '\b\\']
    BACKSPACE = '\b'

    def __init__(self, count, increase=2, steps=10):
        self.count = count
        self.done = 0
        self.rotor_index = 0
        self.increase = increase
        self.steps = steps
        self.bar = ''

    def progress_count(self):
        return self.done

    def rotor_print(self):
        print(self.ROTOR[self.rotor_index], end='', flush=True)
        self.rotor_index = self.rotor_index + 1
        if self.rotor_index == len(self.ROTOR):
            self.rotor_index = 0

    def clean(self):
        cleaner = []
        while len(cleaner) < len(self.bar):
            cleaner.append(self.BACKSPACE)
        print(''.join(cleaner), end='')

    def print_bar(self):
        self.clean()
        print(self.bar, end='', flush=True)

    def step(self):
        if log.getEffectiveLevel() == logging.DEBUG:
            return
        if self.done == 0:
            self.bar += '0%'

        previous = math.floor((float(self.done) / float(self.count)) * 100)
        self.done = self.done + 1
        current = math.floor((float(self.done) / float(self.count)) * 100)

        if previous % self.increase != 0:
            if current % self.increase == 0:
                if previous % self.steps != 0:
                    if current % self.steps == 0:
                        self.bar += '%s%%' % current
                    else:
                        self.bar += self.INCREASE
        self.print_bar()
        self.rotor_print()

    def finish(self):
        self.print_bar()
        print('', flush=True)


class DirData(object):
    @classmethod
    def check_dir(cls, path, file_list):
        for f in file_list:
            if f.startswith(path):
                data = PhotoData.process_file(f)
                if data['ok']:
                    return data['exif']['datetime']
        return None

    @classmethod
    def scan(cls, path, db_file, rebuild=False):
        clean_exit = CleanExit()
        dir_list = {}
        if os.path.isfile(db_file):
            if not rebuild:
                log.info('Updating current Date Map db %s' % db_file)
                dir_list = DirData.load(db_file).db
                log.info('Current Date Map db holds %i direcotry items' % len(list(dir_list.keys())))
            else:
                log.warning('Overwriting current Date Map db %s' % db_file)

        file_list = []
        log.info('Listing all files in %s' % path)
        for root, dirs, files in os.walk(path):
            log.debug('root: %s' % root)
            log.debug('dirs: %s' % dirs)
            log.debug('files: %s' % files)
            for file in files:
                file_list.append(os.path.join(root, file))

        r = re.compile('^%s' % os.path.join(path, ''))
        progress = PrettyProgress(len(file_list))
        dir_read = 0
        log.info('Indexing %i files in %s' % (len(file_list), path))
        for file in file_list:
            progress.step()
            relative_filename = r.sub('', file)
            dir_key = os.path.dirname(relative_filename)
            if dir_key not in dir_list.keys():
                dir_read = dir_read + 1
                timestamp = DirData.check_dir(os.path.join(path, relative_filename), file_list)
                if timestamp is not None:
                    log.debug('found dir %s with date %s' % (dir_key, timestamp))
                    dir_list[dir_key] = timestamp
            else:
                try:
                    date_check = datetime.datetime.strptime(dir_list[dir_key], EXIF_DATETIME_FORMAT)
                    if date_check.year == 0:
                        raise ValueError()
                    else:
                        log.debug('%s already in dir date db' % dir_key)
                except ValueError:
                    dir_read = dir_read + 1
                    timestamp = DirData.check_dir(os.path.join(path, relative_filename), file_list)
                    if timestamp is not None:
                        log.debug('found dir %s with date %s' % (dir_key, timestamp))
                        dir_list[dir_key] = timestamp
            if clean_exit.exit:
                break
        progress.finish()

        log.info('Processed %i files' % progress.progress_count())
        log.info('Needed to check %i directories' % dir_read)
        log.info('Stored %i directories in the database' % len(list(dir_list.keys())))
        return DirData(dir_list, db_file)

    @classmethod
    def load(cls, db_file):
        try:
            with open(db_file, 'r') as f:
                db = json.load(f)
                f.close()
        except Exception as e:
            raise e
        return DirData(db, db_file)

    def __init__(self, db, db_file='dir_list.json'):
        self.db = db
        self.db_file = db_file

    def save(self):
        with open(self.db_file, 'w') as db_file:
            json.dump(self.db, db_file, indent=4)
            db_file.close()

    def get(self, dir_key):
        try:
            return self.db[dir_key]
        except KeyError:
            return None


class PhotoData(object):

    CSV_FIELDNAMES = ['filename', 'has_exif', 'datetime', 'datetime_original',
                      'datetime_digitized', 'ok', 'issue', 'can_fix']

    @classmethod
    def get_exif_from_file(cls, filename):
        with open(filename, 'rb') as image_file:
            try:
                img = exif.Image(image_file)
            except Exception as e:
                image_file.close()
                raise e
            log.debug('has exif: %s' % img.has_exif)
            image_file.close()
        return img

    @classmethod
    def process_file(cls, file_name, base_path=''):
        log.debug('Processing file %s' % file_name)
        r = re.compile('^%s' % os.path.join(base_path, ''))
        file_name = r.sub('', file_name)

        if os.path.basename(file_name).split('.').pop().lower() not in IMAGE_EXTENSIONS:
            return {'filename': file_name, 'ok': False, 'issue': 'NO PICTURE FILE'}
        try:
            img = PhotoData.get_exif_from_file(os.path.join(base_path, file_name))
        except Exception:
            return {'filename': file_name, 'ok': False, 'issue': 'ERROR READING EXIF'}
        data = {
            'filename': file_name,
            'exif': {},
            'has_exif': img.has_exif,
            'ok': False
        }

        if img.has_exif:
#            with warnings.catch_warnings() as w:
                try:
                    data['exif']['datetime'] = img.datetime
                    try:
                        date_check = datetime.datetime.strptime(data['exif']['datetime'], EXIF_DATETIME_FORMAT)
                        log.debug('cheking date %s' % date_check)
                        if date_check.year == 0:
                            raise ValueError()
                    except ValueError:
                        data['exif'] = {}
                        data['issue'] = 'INVALID DATETIME ENTRY'
                        return data
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
                    data['exif']['datetime_digitized'] = img.datetime
        else:
            data['issue'] = 'NO METADATA'
        return data

    @classmethod
    def scan(cls, path, db_file='db.json', rebuild=False):
        clean_exit = CleanExit()
        file_list = []
        log.info('Listing all files in %s' % path)
        for root, dirs, files in os.walk(path):
            for file in files:
                file_list.append(os.path.join(root, file))

        db = {}
        if os.path.isfile(db_file):
            if not rebuild:
                log.info('Updating current Picture db %s' % db_file)
                db = PhotoData.load(path, db_file).db
            else:
                log.warning('Overwriting current Picture db %s' % db_file)

        log.info('Indexing %i files in %s' % (len(file_list), path))
        progress = PrettyProgress(len(file_list))
        r = re.compile('^%s' % os.path.join(path, ''))
        read_count = 0
        for f in file_list:
            progress.step()
            relative_filename = r.sub('', f)
            if relative_filename not in db.keys():
                data = PhotoData.process_file(f, base_path=path)
                db[relative_filename] = data
                read_count = read_count + 1
            elif not db[relative_filename]['ok']:
                data = PhotoData.process_file(f, base_path=path)
                db[relative_filename] = data
                read_count = read_count + 1
            else:
                try:
                    date_check = datetime.datetime.strptime(db[relative_filename]['exif']['datetime'],
                                                            EXIF_DATETIME_FORMAT)
                    if date_check.year == 0:
                        raise ValueError()
                    else:
                        log.debug('%s already in db' % relative_filename)
                except ValueError:
                    data = PhotoData.process_file(f, base_path=path)
                    db[relative_filename] = data
                    read_count = read_count + 1
            if clean_exit.exit:
                break
        progress.finish()
        log.info('Processed %i files' % progress.progress_count())
        log.info('Needed to read EXIF data for %i files' % read_count)

        return PhotoData(path, db, db_file=db_file)

    @classmethod
    def load(cls, path, db_file):
        try:
            log.debug('loading photo db from %s' % db_file)
            with open(db_file, 'r') as f:
                db = json.load(f)
                f.close()
        except Exception as e:
            raise e

        need_save = False
        if isinstance(db, list):
            log.debug('db file is flat file list ... converting ... ')
            new_db = {}
            for f in db:
                new_db[f['filename']] = f
            db = new_db
            need_save = True

        r = re.compile('^%s' % os.path.join(path, ''))
        for f in list(db.keys()):
            if r.match(db[f]['filename']):
                db[f]['filename'] = r.sub('', db[f]['filename'])
                need_save = True
                log.debug('found absolute path in %s filename' % db[f]['filename'])
            if r.match(f):
                log.debug('found absolute path in %s' % f)
                k = r.sub('', f)
                log.debug('%s new key is %s' % (f, k))
                i = db.pop(f)
                i['filename'] = r.sub('', i['filename'])
                db[k] = i
                need_save = True

        fd = PhotoData(path, db, db_file=db_file)
        if need_save:
            log.debug('Saving updated db on load')
            fd.save()
        return fd

    def __init__(self, path, db, db_file='db.json'):
        self.path = path
        self.db = db
        self.db_file = db_file

    def save(self):
        log.info('saving %s' % self.db_file)
        with open(self.db_file, 'w') as f:
            json.dump(self.db, f, indent=4)
            f.close()

    def remove(self, filename=None, regex=None):
        r = None
        if regex is not None:
            log.debug('creating regex for %s' % regex)
            r = re.compile(regex)

        file_count = 0
        for k in list(self.db.keys()):
            remove = False
            if filename is not None:
                if os.path.basename(k) == filename:
                    remove = True
            elif r is not None:
                if r.match(k):
                    remove = True
            if remove:
                log.debug('removing %s' % k)
                self.db.pop(k)
                file_count = file_count + 1
        log.info('Removed %s files from Picture Database' % file_count)

    def problems(self):
        db = {}
        for k in self.db.keys():
            if not self.db[k]['ok']:
                db[k] = self.db[k]
        return PhotoData(self.path, db, '%s.problems' % self.db_file)

    def find_ok_in_dir(self, path):
        for k in self.db.keys():
            if os.path.dirname(k) == path:
                if self.db[k]['ok']:
                    return self.db[k]['exif']['datetime']
        return None

    def dir_date_map(self, date_db):
        log.info('Trying to fix %i DB entries with dir map' % len(list(self.db.keys())))
        progress = PrettyProgress(len(list(self.db.keys())))
        for k in self.db.keys():
            progress.step()
            if not self.db[k]['ok'] and self.db[k]['issue'] in ['NO METADATA',
                                                                'NO DATETIME IN EXIF',
                                                                'ERROR READING EXIF',
                                                                'INVALID DATETIME ENTRY']:
                dir_key = os.path.dirname(k)
                log.debug('looking for %s in date map' % dir_key)
                date = date_db.get(dir_key)
                if date is not None:
                    log.debug('Updating picture file %s metadata to same as dir data %s' % (k, date))
                    self.db[k]['exif'] = {'datetime': date, 'datetime_original': date, 'datetime_digitized': date}
                    self.db[k]['issue'] = 'METADATA MATCHED TO FILES IN SAME DIR'
                else:
                    log.debug('%s not found in directory map' % dir_key)
                    dir_key = os.path.dirname(dir_key)
                    while dir_key != '':
                        log.debug('trying key %s' % dir_key)
                        date = date_db.get(dir_key)
                        if date is not None:
                            log.debug('Updating picture file %s metadata to same as'
                                      'higher level dir %s date is %s' % (k, dir_key, date))
                            self.db[k]['exif'] = {'datetime': date, 'datetime_original': date,
                                                  'datetime_digitized': date}
                            self.db[k]['issue'] = 'METADATA MATCHED TO FILE IN HIGHER DIR %s' % dir_key
                            break
                        dir_key = os.path.dirname(dir_key)
        progress.finish()
        log.info('Processed %i DB entries' % progress.progress_count())

    def fix(self, regex=IMG_FILENAME_REGEX):
        r = re.compile(regex)
        log.info('Trying to fix %i DB entries' % len(list(self.db.keys())))
        progress = PrettyProgress(len(list(self.db.keys())))
        for k in self.db.keys():
            progress.step()
            if not self.db[k]['ok']:
                if self.db[k]['issue'] == 'NO DATETIME IN EXIF':
                    log.debug('checking %s for other metadata' % k)
                    img = PhotoData.get_exif_from_file(os.path.join(self.path, k))
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
                                date = '%s:%s:%s 12:00:00' % (groups[0], groups[1], groups[2])
                                try:
                                    datetime.datetime.strptime(date, EXIF_DATETIME_FORMAT)
                                except ValueError:
                                    log.error('regex match dit not have valid datetime for %s' % date)
                                    continue
                                log.debug('date out of regex is %s' % date)
                                issue = 'DATETIME FOUND IN FILENAME'
                            else:
                                continue
                    log.debug('updating %s datetime to %s' % (k, date))
                    self.db[k]['exif'] = {'datetime': date, 'datetime_original': date, 'datetime_digitized': date}
                    self.db[k]['issue'] = issue
                elif self.db[k]['issue'] == 'NO METADATA':
                    log.debug('no metadata, matching file %s for regex' % k)
                    if r.match(os.path.basename(k)):
                        log.debug('regex matched')
                        groups = r.match(os.path.basename(k)).groups()
                        date = '%s:%s:%s 12:00:00' % (groups[0], groups[1], groups[2])
                        try:
                            datetime.datetime.strptime(date, EXIF_DATETIME_FORMAT)
                            log.debug('date out of regex is %s' % date)
                            issue = 'DATETIME FOUND IN FILENAME'
                            self.db[k]['exif'] = {'datetime': date, 'datetime_original': date,
                                                  'datetime_digitized': date}
                            self.db[k]['issue'] = issue
                        except ValueError:
                            log.error('regex match dit not have valid datetime for %s' % date)
                            continue
            else:
                for entry in ['datetime_original', 'datetime_digitized']:
                    try:
                        date_check = datetime.datetime.strptime(self.db[k]['exif'][entry], EXIF_DATETIME_FORMAT)
                        if date_check.year == 0:
                            raise ValueError()
                    except ValueError:
                        log.debug('%s has invalid datetime, copying from datetime entry' % entry)
                        self.db[k]['exif'][entry] = self.db[k]['exif']['datetime']

        progress.finish()
        log.info('Processed %i DB entries' % progress.progress_count())

    def csv_write(self, filename, **kwargs):
        with open(filename, 'w') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=self.CSV_FIELDNAMES)
            csv_writer.writeheader()
            for i in self:
                i['can_fix'] = None
                if not i['ok']:
                    if i['issue'] not in ['NO PICTURE FILE', 'NO METADATA', 'NO DATETIME IN EXIF', 'INVALID DATETIME ENTRY']:
                        i['can_fix'] = True
                    else:
                        i['can_fix'] = False

                do_write = True
                for key in kwargs:
                    match = True
                    s_key = key
                    if key.endswith('!'):
                        match = False
                        s_key = key.replace('!', '')

                    try:
                        if isinstance(i[s_key], bool):
                            if kwargs[key].lower() in ['y', 'yes', 'true']:
                                value = True
                            else:
                                value = False
                        else:
                            if kwargs[key].lower() in ['null', 'none']:
                                value = None
                            else:
                                value = kwargs[key]

                        if match and i[s_key] != value:
                            do_write = False
                        if not match and i[s_key] == value:
                            do_write = False
                    except KeyError as e:
                        log.error('no key %s' % e)
                        sys.exit(1)

                if do_write:
                    csv_writer.writerow(i)

            csv_file.close()

    def update_from_file(self, filename, field='issue', value='MANUAL FIX', force=False):
        with open(filename, 'r') as csv_file:
            reader = csv.DictReader(csv_file, fieldnames=self.CSV_FIELDNAMES)
            for i in reader:
                if i[field] == value:
                    f = i['filename']
                    log.debug('Item marked for manual update: %s' % f)
                    try:
                        try:
                            if not self.db[f]['ok']:
                                log.debug('entry in db selected for manual update as no automatic fix could be found')

                                if 'exif' not in self.db[f].keys():
                                    log.debug('no exif for db entry yet creating')
                                    self.db[f]['exif'] = {'datetime': None, 'datetime_original': None,
                                                          'datetime_digitized': None}
                                elif 'datetime' not in self.db[f]['exif'].keys():
                                    log.debug('no datetime key in current exif creating')
                                    self.db[f]['exif'] = {'datetime': None, 'datetime_original': None,
                                                          'datetime_digitized': None}
                                else:
                                    log.debug('current exif: %s' % self.db[f]['exif'])

                                if self.db[f]['exif']['datetime'] is None or force:
                                    log.debug('loading datetime for manual update file')
                                    date = i['datetime']
                                    log.debug('found %s' % date)
                                    if i['datetime_original'] is not None and i['datetime_original'] != '':
                                        date_original = i['datetime_original']
                                    else:
                                        date_original = date
                                    if i['datetime_digitized'] is not None and i['datetime_digitized'] != '':
                                        date_digitized = i['datetime_digitized']
                                    else:
                                        date_digitized = date
                                    log.info('updating %s to datetime %s' % (f, date))
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
                                    log.warning('not updating entry %s as there is already a date set %s.'
                                                'use --force to overwrite' % (f, self.db[f]['exif']['datetime']))
                            else:
                                log.info('a fix was already done for %s use --force to overwrite' % f)
                        except KeyError as e:
                            log.error('something wend wrong: %s' % e)
                            sys.exit(1)
                    except KeyError:
                        log.warning('Entry %s not found in picture database' % f)

    def add(self, filename, force=False):
        r = re.compile('^%s' % os.path.join(self.path, ''))
        if r.match(filename):
            filename = r.sub('', filename)
        if filename in self.db.keys():
            if not force:
                log.warning('%s already in DB use --force to overwrite' % filename)
            else:
                data = PhotoData.process_file(os.path.join(self.path, filename), base_path=self.path)
                log.info('adding %s to DB' % filename)
                self.db[filename] = data

    def __str__(self):
        out = '%-40s%-6s%-20s%-6s%-30s\n' % ('FILENAME', 'EXIF', 'DATETIME', 'OK', 'ISSUE')
        out += '\n'
        for i in self:
            out += '%-40s%-6s%-20s%-6s%-30s\n' % (i['filename'], i['has_exif'], i['datetime'], i['ok'], i['issue'])
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

    def __len__(self):
        return len(list(self.db.keys()))


class PictureUpdater(object):
    def __init__(self, db, path='.'):
        self.db = db
        self.dir = path
        self.EXIT = CleanExit()

    def write_fixes(self, force=False):
        write_counter = 0
        file_counter = 0
        progress = PrettyProgress(len(self.db))
        if not force:
            log.warning('not really writing files, use --force')
        log.info('Processing %i files for update' % len(self.db))
        for picture in self.db:
            progress.step()
            if self.EXIT.exit:
                break

            if picture['datetime'] is None:
                log.debug('not touching %s as no datetime in db' % picture['filename'])
                continue
            filename = os.path.join(self.dir, picture['filename'])
            date = picture['datetime']
            try:
                datetime.datetime.strptime(date, EXIF_DATETIME_FORMAT)
            except ValueError:
                log.error('Datetime % is not a valid datetime to format %s' % (date, EXIF_DATETIME_FORMAT))
                sys.exit(1)
            log.debug('Updating %s' % filename)

            if os.path.isfile(filename):
                file_counter = file_counter + 1
                with open(filename, 'rb') as f:
                    img = exif.Image(f)
                    f.close()
                log.debug('updating exif to date %s' % date)
                if not img.has_exif:
                    log.warning('\nOriginal file %s has no exif need to create' % filename)
                else:
                    if 'datetime' not in list(dir(img)):
                        log.warning('\nOriginal file %s has exif without datetime field' % filename)
                        img.set('datetime', date)
                    else:
                        log.debug('Original file has exif')
                        if img.datetime == date:
                            log.debug('Image already on correct timestamp')
                            continue
                img.datetime = date
                if 'datetime_original' in list(dir(img)):
                    img.datetime_original = date
                if 'datetime_digitized' in list(dir(img)):
                    img.datetime_digitized = date
                if force:
                    log.info('writing file %s' % filename)
                    with open(filename, 'wb') as new_file:
                        new_file.write(img.get_file())
                        new_file.close()
                        write_counter = write_counter + 1
            else:
                log.warning('picture %s in db not on filesystem' % filename)
        progress.finish()
        log.info('Processed %i files for updating' % progress.progress_count())
        log.info('%i files needed updating' % file_counter)
        if force:
            log.info('%i files written' % write_counter)


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', help='debug output', action='store_true')
    parser.add_argument('--date-map', help='dir date map', default='dir_list.json')
    parser.add_argument('--picture-database', help='picture db file', default='db.json')
    parser.add_argument('-d', '--dir', help='process entire dir', required=True)

    command = parser.add_subparsers(dest='command', metavar='command', required=True)

    lister = command.add_parser('list', help='List the Picture Database')
    lister.add_argument('-o', '--out', help='output to csv')
    lister.add_argument('--filter', help='filter output with field=value,field2=value2,...')

    issues = command.add_parser('issues', help='list the problematic files in the Picture Database')
    issues.add_argument('-o', '--out', help='output to csv')
    issues.add_argument('--filter', help='filter output with field=value,field2=value2,...')

    remove = command.add_parser('remove', help='remove file(s) from Picture Database')
    selector = remove.add_mutually_exclusive_group(required=False)
    selector.add_argument('-n', '--name', help='filename selector')
    selector.add_argument('-r', '--regex', help='regex selector')

    add = command.add_parser('add', help='add single file to Picture Database')
    add.add_argument('-n', '--name', help='filename', required=True)
    add.add_argument('--force', help='force db update', action='store_true')

    create = command.add_parser('create', help='create data map')
    create.add_argument('--rebuild', help='rebuild existing db', action='store_true')
    create.add_argument('--force', help='force file overwrite', action='store_true')

    scan = command.add_parser('scan', help='create picture database')
    scan.add_argument('--rebuild', help='rebuild existing db', action='store_true')
    scan.add_argument('--force', help='force file overwrite', action='store_true')

    command.add_parser('map', help='map directory date db over file')

    info = command.add_parser('info', help='get exif info')
    info.add_argument('-f', '--file', help='filename', required=True)

    fix = command.add_parser('fix', help='run fixes')
    fix.add_argument('--regex', help='set regex to find dates in files', default=IMG_FILENAME_REGEX)

    update = command.add_parser('update', help='update manual fixes from a issues csv')
    update.add_argument('-i', '--input', help='input issues.csv', required=True)
    update.add_argument('--force', help='force update', action='store_true')

    write = command.add_parser('write', help='write fixed metadata to files')
    write.add_argument('--force', help='force update', action='store_true')

    return parser.parse_args()


def main():
    args = get_parser()

    if args.verbose:
        log.setLevel(logging.DEBUG)
        log.debug('Debug logging enabled')

    if args.command == 'info':
        img = PhotoData.get_exif_from_file(args.file)
        print(dir(img))
        sys.exit(0)

    out_filter = {}
    try:
        if args.filter is not None:
            filter_list = args.filter.split(',')
            for i in filter_list:
                key = i.split('=')[0]
                value = ''.join(i.split('=')[1:])
                out_filter[key] = value
    except AttributeError:
        pass

    if args.command == 'create' and args.dir is not None:
        log.info('Creating Directory Date map for %s' % args.dir)
        if os.path.isfile(args.date_map):
            log.warning('Date DB already exists')
            if not args.force:
                log.error('Not overwriting (use --force)')
                sys.exit(1)
        dir_data = DirData.scan(args.dir, args.date_map, rebuild=args.rebuild)
        dir_data.save()
    elif args.command == 'scan':
        if os.path.isfile(args.picture_database):
            log.warning('DB already exists')
            if not args.force:
                log.error('Not overwriting (use --force)')
                sys.exit(1)
        log.info('Creating picture database for %s' % args.dir)
        photo_db = PhotoData.scan(args.dir, args.picture_database, rebuild=args.rebuild)
        photo_db.save()
    else:
        if not os.path.isfile(args.picture_database):
            log.error('No picture database %s found. Run scan first' % args.picture_database)
            sys.exit(1)
        if not os.path.isfile(args.date_map):
            log.error('No directory data map %s found. Run create first' % args.date_map)
            sys.exit(1)
        photo_db = PhotoData.load(args.dir, args.picture_database)
        dir_db = DirData.load(args.date_map)

        if args.command == 'list':
            if args.out is not None:
                photo_db.csv_write(args.out, **out_filter)
            else:
                print('%s' % photo_db)
        if args.command == 'issues':
            p = photo_db.problems()
            if args.out is None:
                print('%s' % p)
            else:
                p.csv_write(args.out, **out_filter)
        if args.command == 'remove':
            photo_db.remove(filename=args.name, regex=args.regex)
            photo_db.save()
        if args.command == 'map':
            photo_db.dir_date_map(dir_db)
            photo_db.save()
        if args.command == 'fix':
            photo_db.fix(regex=args.regex)
            photo_db.save()
        if args.command == 'update':
            photo_db.update_from_file(args.input, force=args.force)
            photo_db.save()
        if args.command == 'write':
            problems = photo_db.problems()
            PictureUpdater(problems, path=str(args.dir)).write_fixes(force=args.force)
        if args.command == 'add':
            photo_db.add(args.name, force=args.force)
            photo_db.save()


if '__main__' in __name__:
    log.info('START RUN')
    main()
    log.info('STOP RUN')
