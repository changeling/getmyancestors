#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
   getmyancestors.py - Retrieve GEDCOM data from FamilySearch Tree
   Copyright (C) 2014-2016 Giulio Genovese (giulio.genovese@gmail.com)

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.

   Written by Giulio Genovese <giulio.genovese@gmail.com>
   and by Benoît Fontaine <benoitfontaine.ba@gmail.com>
"""

# global import
from __future__ import print_function
import sys
import argparse
import getpass
import time
import asyncio
import re

# local import
from translation import translations

try:
    import requests
except ImportError:
    sys.stderr.write('You need to install the requests module first\n')
    sys.stderr.write('(run this in your terminal: "python3 -m pip install requests" or "python3 -m pip install --user requests")\n')
    exit(2)

try:
    import babelfish
except ImportError:
    sys.stderr.write('You need to install the babelfish module first\n')
    sys.stderr.write('(run this in your terminal: "python3 -m pip install babelfish" or "python3 -m pip install --user babelfish")\n')
    exit(2)

MAX_PERSONS = 200  # is subject to change: see https://www.familysearch.org/developers/docs/api/tree/Persons_resource

FACT_TAGS = {
    'http://gedcomx.org/Birth': 'BIRT',
    'http://gedcomx.org/Christening': 'CHR',
    'http://gedcomx.org/Death': 'DEAT',
    'http://gedcomx.org/Burial': 'BURI',
    'http://gedcomx.org/PhysicalDescription': 'DSCR',
    'http://gedcomx.org/Occupation': 'OCCU',
    'http://gedcomx.org/MilitaryService': '_MILT',
    'http://gedcomx.org/Marriage': 'MARR',
    'http://gedcomx.org/Divorce': 'DIV',
    'http://gedcomx.org/Annulment': 'ANUL',
    'http://gedcomx.org/CommonLawMarriage': '_COML',
    'http://gedcomx.org/BarMitzvah': 'BARM',
    'http://gedcomx.org/BatMitzvah': 'BASM',
    'http://gedcomx.org/Naturalization': 'NATU',
    'http://gedcomx.org/Residence': 'RESI',
    'http://gedcomx.org/Religion': 'RELI',
    'http://familysearch.org/v1/TitleOfNobility': 'TITL',
    'http://gedcomx.org/Cremation': 'CREM',
    'http://gedcomx.org/Caste': 'CAST',
    'http://gedcomx.org/Nationality': 'NATI',
}

FACT_EVEN = {
    'http://gedcomx.org/Stillbirth': 'Stillborn',
    'http://familysearch.org/v1/Affiliation': 'Affiliation',
    'http://gedcomx.org/Clan': 'Clan Name',
    'http://gedcomx.org/NationalId': 'National Identification',
    'http://gedcomx.org/Ethnicity': 'Race',
    'http://familysearch.org/v1/TribeName': 'Tribe Name'
}

ORDINANCES_STATUS = {
    'http://familysearch.org/v1/Ready': 'QUALIFIED',
    'http://familysearch.org/v1/Completed': 'COMPLETED',
    'http://familysearch.org/v1/Cancelled': 'CANCELED',
    'http://familysearch.org/v1/InProgress': 'SUBMITTED',
    'http://familysearch.org/v1/NotNeeded': 'INFANT'
}


def cont(string):
    level = int(string[:1]) + 1
    lines = string.splitlines()
    res = list()
    max_len = 255
    for line in lines:
        c_line = line
        to_conc = list()
        while len(c_line.encode('utf-8')) > max_len:
            index = min(max_len, len(c_line) - 2)
            while (len(c_line[:index].encode('utf-8')) > max_len or re.search(r'[ \t\v]', c_line[index - 1:index + 1])) and index > 1:
                index -= 1
            to_conc.append(c_line[:index])
            c_line = c_line[index:]
            max_len = 248
        to_conc.append(c_line)
        res.append(('\n%s CONC ' % level).join(to_conc))
        max_len = 248
    return ('\n%s CONT ' % level).join(res)


# FamilySearch session class
class Session:
    def __init__(self, username, password, verbose=False, logfile=sys.stderr, timeout=60):
        self.username = username
        self.password = password
        self.verbose = verbose
        self.logfile = logfile
        self.timeout = timeout
        self.fid = self.lang = self.display_name = None
        self.counter = 0
        self.logged = self.login()

    # Write in logfile if verbose enabled
    def write_log(self, text):
        if self.verbose:
            self.logfile.write('[%s]: %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), text))

    # retrieve FamilySearch session ID (https://familysearch.org/developers/docs/guides/oauth2)
    def login(self):
        while True:
            try:
                url = 'https://www.familysearch.org/auth/familysearch/login'
                self.write_log('Downloading: ' + url)
                r = requests.get(url, params={'ldsauth': False}, allow_redirects=False)
                url = r.headers['Location']
                self.write_log('Downloading: ' + url)
                r = requests.get(url, allow_redirects=False)
                idx = r.text.index('name="params" value="')
                span = r.text[idx + 21:].index('"')
                params = r.text[idx + 21:idx + 21 + span]

                url = 'https://ident.familysearch.org/cis-web/oauth2/v3/authorization'
                self.write_log('Downloading: ' + url)
                r = requests.post(url, data={'params': params, 'userName': self.username, 'password': self.password}, allow_redirects=False)

                if 'The username or password was incorrect' in r.text:
                    self.write_log('The username or password was incorrect')
                    return False

                if 'Invalid Oauth2 Request' in r.text:
                    self.write_log('Invalid Oauth2 Request')
                    time.sleep(self.timeout)
                    continue

                url = r.headers['Location']
                self.write_log('Downloading: ' + url)
                r = requests.get(url, allow_redirects=False)
                self.fssessionid = r.cookies['fssessionid']
            except requests.exceptions.ReadTimeout:
                self.write_log('Read timed out')
                continue
            except requests.exceptions.ConnectionError:
                self.write_log('Connection aborted')
                time.sleep(self.timeout)
                continue
            except requests.exceptions.HTTPError:
                self.write_log('HTTPError')
                time.sleep(self.timeout)
                continue
            except KeyError:
                self.write_log('KeyError')
                time.sleep(self.timeout)
                continue
            except ValueError:
                self.write_log('ValueError')
                time.sleep(self.timeout)
                continue
            self.write_log('FamilySearch session id: ' + self.fssessionid)
            return True

    # retrieve JSON structure from FamilySearch URL
    def get_url(self, url):
        self.counter += 1
        while True:
            try:
                self.write_log('Downloading: ' + url)
                # r = requests.get(url, cookies = { 's_vi': self.s_vi, 'fssessionid' : self.fssessionid }, timeout = self.timeout)
                r = requests.get('https://familysearch.org' + url, cookies={'fssessionid': self.fssessionid}, timeout=self.timeout)
            except requests.exceptions.ReadTimeout:
                self.write_log('Read timed out')
                continue
            except requests.exceptions.ConnectionError:
                self.write_log('Connection aborted')
                time.sleep(self.timeout)
                continue
            self.write_log('Status code: ' + str(r.status_code))
            if r.status_code == 204:
                return None
            if r.status_code in {404, 405, 410, 500}:
                self.write_log('WARNING: ' + url)
                return None
            if r.status_code == 401:
                self.login()
                continue
            try:
                r.raise_for_status()
            except requests.exceptions.HTTPError:
                self.write_log('HTTPError')
                if r.status_code == 403:
                    if 'message' in r.json()['errors'][0] and r.json()['errors'][0]['message'] == u'Unable to get ordinances.':
                        self.write_log('Unable to get ordinances. Try with an LDS account or without option -c.')
                        return 'error'
                    else:

                        self.write_log('WARNING: code 403 from %s %s' % (url, r.json()['errors'][0]['message'] or ''))
                        return None
                time.sleep(self.timeout)
                continue
            try:
                return r.json()
            except Exception as e:
                self.write_log('WARNING: corrupted file from %s, error: %s' % (url, e))
                return None

    # retrieve FamilySearch current user ID
    def set_current(self):
        url = '/platform/users/current.json'
        data = self.get_url(url)
        if data:
            self.fid = data['users'][0]['personId']
            self.lang = data['users'][0]['preferredLanguage']
            self.display_name = data['users'][0]['displayName']

    def get_userid(self):
        if not self.fid:
            self.set_current()
        return self.fid

    def _(self, string):
        if not self.lang:
            self.set_current()
        if string in translations and self.lang in translations[string]:
            return translations[string][self.lang]
        return string


# some GEDCOM objects
class Note:

    counter = 0

    def __init__(self, text='', tree=None, num=None):
        if num:
            self.num = num
        else:
            Note.counter += 1
            self.num = Note.counter
        self.text = text.strip()

        if tree:
            tree.notes.append(self)

    def print(self, file=sys.stdout):
        file.write(cont('0 @N' + str(self.num) + '@ NOTE ' + self.text) + '\n')

    def link(self, file=sys.stdout, level=1):
        file.write(str(level) + ' NOTE @N' + str(self.num) + '@\n')


class Source:

    counter = 0

    def __init__(self, data=None, tree=None, num=None):
        if num:
            self.num = num
        else:
            Source.counter += 1
            self.num = Source.counter

        self.tree = tree
        self.url = self.citation = self.title = self.fid = None
        self.notes = set()
        if data:
            self.fid = data['id']
            if 'about' in data:
                self.url = data['about'].replace('familysearch.org/platform/memories/memories', 'www.familysearch.org/photos/artifacts')
            if 'citations' in data:
                self.citation = data['citations'][0]['value']
            if 'titles' in data:
                self.title = data['titles'][0]['value']
            if 'notes' in data:
                for n in data['notes']:
                    if n['text']:
                        self.notes.add(Note(n['text'], self.tree))

    def print(self, file=sys.stdout):
        file.write('0 @S' + str(self.num) + '@ SOUR \n')
        if self.title:
            file.write(cont('1 TITL ' + self.title) + '\n')
        if self.citation:
            file.write(cont('1 AUTH ' + self.citation) + '\n')
        if self.url:
            file.write(cont('1 PUBL ' + self.url) + '\n')
        for n in self.notes:
            n.link(file, 1)
        file.write('1 REFN ' + self.fid + '\n')

    def link(self, file=sys.stdout, level=1):
        file.write(str(level) + ' SOUR @S' + str(self.num) + '@\n')


class Fact:

    def __init__(self, data=None, tree=None):
        self.value = self.type = self.date = self.place = self.note = self.map = None
        if data:
            if 'value' in data:
                self.value = data['value']
            if 'type' in data:
                self.type = data['type']
                if self.type in FACT_EVEN:
                    self.type = tree.fs._(FACT_EVEN[self.type])
                elif self.type[:6] == u'data:,':
                    self.type = self.type[6:]
                elif self.type not in FACT_TAGS:
                    self.type = None
            if 'date' in data:
                self.date = data['date']['original']
            if 'place' in data:
                place = data['place']
                self.place = place['original']
                if 'description' in place and place['description'][1:] in tree.places:
                    self.map = tree.places[place['description'][1:]]
            if 'changeMessage' in data['attribution']:
                self.note = Note(data['attribution']['changeMessage'], tree)
            if self.type == 'http://gedcomx.org/Death' and not (self.date or self.place):
                self.value = 'Y'

    def print(self, file=sys.stdout, key=None):
        if self.type in FACT_TAGS:
            tmp = '1 ' + FACT_TAGS[self.type]
            if self.value:
                tmp += ' ' + self.value
            file.write(cont(tmp))
        elif self.type:
            file.write('1 EVEN\n2 TYPE ' + self.type)
            if self.value:
                file.write('\n' + cont('2 NOTE Description: ' + self.value))
        else:
            return
        file.write('\n')
        if self.date:
            file.write(cont('2 DATE ' + self.date) + '\n')
        if self.place:
            file.write(cont('2 PLAC ' + self.place) + '\n')
        if self.map:
            latitude, longitude = self.map
            file.write('3 MAP\n4 LATI ' + latitude + '\n4 LONG ' + longitude + '\n')
        if self.note:
            self.note.link(file, 2)


class Memorie:

    def __init__(self, data=None):
        self.description = self.url = None
        if data and 'links' in data:
            self.url = data['about']
            if 'titles' in data:
                self.description = data['titles'][0]['value']
            if 'descriptions' in data:
                self.description = ('' if not self.description else self.description + '\n') + data['descriptions'][0]['value']

    def print(self, file=sys.stdout):
        file.write('1 OBJE\n2 FORM URL\n')
        if self.description:
            file.write(cont('2 TITL ' + self.description) + '\n')
        if self.url:
            file.write(cont('2 FILE ' + self.url) + '\n')


class Name:

    def __init__(self, data=None, tree=None):
        self.given = ''
        self.surname = ''
        self.prefix = None
        self.suffix = None
        self.note = None
        if data:
            if 'parts' in data['nameForms'][0]:
                for z in data['nameForms'][0]['parts']:
                    if z['type'] == u'http://gedcomx.org/Given':
                        self.given = z['value']
                    if z['type'] == u'http://gedcomx.org/Surname':
                        self.surname = z['value']
                    if z['type'] == u'http://gedcomx.org/Prefix':
                        self.prefix = z['value']
                    if z['type'] == u'http://gedcomx.org/Suffix':
                        self.suffix = z['value']
            if 'changeMessage' in data['attribution']:
                self.note = Note(data['attribution']['changeMessage'], tree)

    def print(self, file=sys.stdout, typ=None):
        tmp = '1 NAME ' + self.given + ' /' + self.surname + '/'
        if self.suffix:
            tmp += ' ' + self.suffix
        file.write(cont(tmp) + '\n')
        if typ:
            file.write('2 TYPE ' + typ + '\n')
        if self.prefix:
            file.write('2 NPFX ' + self.prefix + '\n')
        if self.note:
            self.note.link(file, 2)


class Ordinance:

    def __init__(self, data=None):
        self.date = self.temple_code = self.status = self.famc = None
        if data:
            if 'date' in data:
                self.date = data['date']['formal']
            if 'templeCode' in data:
                self.temple_code = data['templeCode']
            self.status = data['status']

    def print(self, file=sys.stdout):
        if self.date:
            file.write(cont('2 DATE ' + self.date) + '\n')
        if self.temple_code:
            file.write('2 TEMP ' + self.temple_code + '\n')
        if self.status in ORDINANCES_STATUS:
            file.write('2 STAT ' + ORDINANCES_STATUS[self.status] + '\n')
        if self.famc:
            file.write('2 FAMC @F' + str(self.famc.num) + '@\n')


# GEDCOM individual class
class Indi:

    counter = 0

    # initialize individual
    def __init__(self, fid=None, tree=None, num=None):
        if num:
            self.num = num
        else:
            Indi.counter += 1
            self.num = Indi.counter
        self.fid = fid
        self.tree = tree
        self.famc_fid = set()
        self.fams_fid = set()
        self.famc_num = set()
        self.fams_num = set()
        self.name = None
        self.gender = None
        self.parents = set()
        self.spouses = set()
        self.children = set()
        self.baptism = self.confirmation = self.endowment = self.sealing_child = None
        self.nicknames = set()
        self.facts = set()
        self.birthnames = set()
        self.married = set()
        self.aka = set()
        self.notes = set()
        self.sources = set()
        self.memories = set()

    def add_data(self, data):
        if data:
            if data['names']:
                for x in data['names']:
                    if x['preferred']:
                        self.name = Name(x, self.tree)
                    else:
                        if x['type'] == u'http://gedcomx.org/Nickname':
                            self.nicknames.add(Name(x, self.tree))
                        if x['type'] == u'http://gedcomx.org/BirthName':
                            self.birthnames.add(Name(x, self.tree))
                        if x['type'] == u'http://gedcomx.org/AlsoKnownAs':
                            self.aka.add(Name(x, self.tree))
                        if x['type'] == u'http://gedcomx.org/MarriedName':
                            self.married.add(Name(x, self.tree))
            if 'gender' in data:
                if data['gender']['type'] == 'http://gedcomx.org/Male':
                    self.gender = 'M'
                elif data['gender']['type'] == 'http://gedcomx.org/Female':
                    self.gender = 'F'
                elif data['gender']['type'] == 'http://gedcomx.org/Unknown':
                    self.gender = 'U'
            if 'facts' in data:
                for x in data['facts']:
                    if x['type'] == u'http://familysearch.org/v1/LifeSketch':
                        self.notes.add(Note('=== ' + self.tree.fs._('Life Sketch') + ' ===\n' + x['value'], self.tree))
                    else:
                        self.facts.add(Fact(x, self.tree))
            if 'sources' in data:
                sources = self.tree.fs.get_url('/platform/tree/persons/%s/sources.json' % self.fid)
                if sources:
                    quotes = dict()
                    for quote in sources['persons'][0]['sources']:
                        quotes[quote['descriptionId']] = quote['attribution']['changeMessage'] if 'changeMessage' in quote['attribution'] else None
                    for source in sources['sourceDescriptions']:
                        if source['id'] not in self.tree.sources:
                            self.tree.sources[source['id']] = Source(source, self.tree)
                        self.sources.add((self.tree.sources[source['id']], quotes[source['id']]))
            if 'evidence' in data:
                url = '/platform/tree/persons/%s/memories.json' % self.fid
                memorie = self.tree.fs.get_url(url)
                if memorie and 'sourceDescriptions' in memorie:
                    for x in memorie['sourceDescriptions']:
                        if x['mediaType'] == 'text/plain':
                            text = '\n'.join(val.get('value', '') for val in x.get('titles', []) + x.get('descriptions', []))
                            self.notes.add(Note(text, self.tree))
                        else:
                            self.memories.add(Memorie(x))

    # add a fams to the individual
    def add_fams(self, fams):
        self.fams_fid.add(fams)

    # add a famc to the individual
    def add_famc(self, famc):
        self.famc_fid.add(famc)

    # retrieve individual notes
    def get_notes(self):
        notes = self.tree.fs.get_url('/platform/tree/persons/%s/notes.json' % self.fid)
        if notes:
            for n in notes['persons'][0]['notes']:
                text_note = '=== ' + n['subject'] + ' ===\n' if 'subject' in n else ''
                text_note += n['text'] + '\n' if 'text' in n else ''
                self.notes.add(Note(text_note, self.tree))

    # retrieve LDS ordinances
    def get_ordinances(self):
        res = []
        famc = False
        url = '/platform/tree/persons/%s/ordinances.json' % self.fid
        data = self.tree.fs.get_url(url)['persons'][0]['ordinances']
        if data:
            for o in data:
                if o['type'] == u'http://lds.org/Baptism':
                    self.baptism = Ordinance(o)
                elif o['type'] == u'http://lds.org/Confirmation':
                    self.confirmation = Ordinance(o)
                elif o['type'] == u'http://lds.org/Endowment':
                    self.endowment = Ordinance(o)
                elif o['type'] == u'http://lds.org/SealingChildToParents':
                    self.sealing_child = Ordinance(o)
                    if 'father' in o and 'mother' in o:
                        famc = (o['father']['resourceId'],
                                o['mother']['resourceId'])
                elif o['type'] == u'http://lds.org/SealingToSpouse':
                    res.append(o)
        return res, famc

    # retrieve contributors
    def get_contributors(self):
        temp = set()
        data = self.tree.fs.get_url('/platform/tree/persons/%s/changes.json' % self.fid)
        if data:
            for entries in data['entries']:
                for contributors in entries['contributors']:
                    temp.add(contributors['name'])
        if temp:
            text = '=== ' + self.tree.fs._('Contributors') + ' ===\n' + '\n'.join(sorted(temp))
            for n in self.tree.notes:
                if n.text == text:
                    self.notes.add(n)
                    return
            self.notes.add(Note(text, self.tree))

    # print individual information in GEDCOM format
    def print(self, file=sys.stdout):
        file.write('0 @I' + str(self.num) + '@ INDI\n')
        if self.name:
            self.name.print(file)
        for o in self.nicknames:
            file.write(cont('2 NICK ' + o.given + ' ' + o .surname) + '\n')
        for o in self.birthnames:
            o.print(file)
        for o in self.aka:
            o.print(file, 'aka')
        for o in self.married:
            o.print(file, 'married')
        if self.gender:
            file.write('1 SEX ' + self.gender + '\n')
        for o in self.facts:
            o.print(file)
        for o in self.memories:
            o.print(file)
        if self.baptism:
            file.write('1 BAPL\n')
            self.baptism.print(file)
        if self.confirmation:
            file.write('1 CONL\n')
            self.confirmation.print(file)
        if self.endowment:
            file.write('1 ENDL\n')
            self.endowment.print(file)
        if self.sealing_child:
            file.write('1 SLGC\n')
            self.sealing_child.print(file)
        for num in self.fams_num:
            file.write('1 FAMS @F' + str(num) + '@\n')
        for num in self.famc_num:
            file.write('1 FAMC @F' + str(num) + '@\n')
        file.write('1 _FSFTID ' + self.fid + '\n')
        for o in self.notes:
            o.link(file)
        for source, quote in self.sources:
            source.link(file, 1)
            if quote:
                file.write(cont('2 PAGE ' + quote) + '\n')


# GEDCOM family class
class Fam:
    counter = 0

    # initialize family
    def __init__(self, husb=None, wife=None, tree=None, num=None):
        if num:
            self.num = num
        else:
            Fam.counter += 1
            self.num = Fam.counter
        self.husb_fid = husb if husb else None
        self.wife_fid = wife if wife else None
        self.tree = tree
        self.husb_num = self.wife_num = self.fid = None
        self.facts = set()
        self.sealing_spouse = None
        self.chil_fid = set()
        self.chil_num = set()
        self.notes = set()
        self.sources = set()

    # add a child to the family
    def add_child(self, child):
        if child not in self.chil_fid:
            self.chil_fid.add(child)

    # retrieve and add marriage information
    def add_marriage(self, fid):
        if not self.fid:
            self.fid = fid
            url = '/platform/tree/couple-relationships/%s.json' % self.fid
            data = self.tree.fs.get_url(url)
            if data:
                if 'facts' in data['relationships'][0]:
                    for x in data['relationships'][0]['facts']:
                        self.facts.add(Fact(x, self.tree))
                if 'sources' in data['relationships'][0]:
                    quotes = dict()
                    for x in data['relationships'][0]['sources']:
                        quotes[x['descriptionId']] = x['attribution']['changeMessage'] if 'changeMessage' in x['attribution'] else None
                    new_sources = quotes.keys() - self.tree.sources.keys()
                    if new_sources:
                        sources = self.tree.fs.get_url('/platform/tree/couple-relationships/%s/sources.json' % self.fid)
                        for source in sources['sourceDescriptions']:
                            if source['id'] in new_sources and source['id'] not in self.tree.sources:
                                self.tree.sources[source['id']] = Source(source, self.tree)
                    for source_fid in quotes:
                        self.sources.add((self.tree.sources[source_fid], quotes[source_fid]))

    # retrieve marriage notes
    def get_notes(self):
        if self.fid:
            notes = self.tree.fs.get_url('/platform/tree/couple-relationships/%s/notes.json' % self.fid)
            if notes:
                for n in notes['relationships'][0]['notes']:
                    text_note = '=== ' + n['subject'] + ' ===\n' if 'subject' in n else ''
                    text_note += n['text'] + '\n' if 'text' in n else ''
                    self.notes.add(Note(text_note, self.tree))

    # retrieve contributors
    def get_contributors(self):
        if self.fid:
            temp = set()
            data = self.tree.fs.get_url('/platform/tree/couple-relationships/%s/changes.json' % self.fid)
            if data:
                for entries in data['entries']:
                    for contributors in entries['contributors']:
                        temp.add(contributors['name'])
            if temp:
                text = '=== ' + self.tree.fs._('Contributors') + ' ===\n' + '\n'.join(sorted(temp))
                for n in self.tree.notes:
                    if n.text == text:
                        self.notes.add(n)
                        return
                self.notes.add(Note(text, self.tree))

    # print family information in GEDCOM format
    def print(self, file=sys.stdout):
        file.write('0 @F' + str(self.num) + '@ FAM\n')
        if self.husb_num:
            file.write('1 HUSB @I' + str(self.husb_num) + '@\n')
        if self.wife_num:
            file.write('1 WIFE @I' + str(self.wife_num) + '@\n')
        for num in self.chil_num:
            file.write('1 CHIL @I' + str(num) + '@\n')
        for o in self.facts:
            o.print(file)
        if self.sealing_spouse:
            file.write('1 SLGS\n')
            self.sealing_spouse.print(file)
        if self.fid:
            file.write('1 _FSFTID ' + self.fid + '\n')
        for o in self.notes:
            o.link(file)
        for source, quote in self.sources:
            source.link(file, 1)
            if quote:
                file.write(cont('2 PAGE ' + quote) + '\n')


# family tree class
class Tree:
    def __init__(self, fs=None):
        self.fs = fs
        self.indi = dict()
        self.fam = dict()
        self.notes = list()
        self.sources = dict()
        self.places = dict()

    # add individuals to the family tree
    def add_indis(self, fids):
        async def add_datas(loop, data):
            futures = set()
            for person in data['persons']:
                self.indi[person['id']] = Indi(person['id'], self)
                futures.add(loop.run_in_executor(None, self.indi[person['id']].add_data, person))
            for future in futures:
                await future

        new_fids = [fid for fid in fids if fid and fid not in self.indi]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # loop = asyncio.get_event_loop()
        while len(new_fids):
            data = self.fs.get_url('/platform/tree/persons.json?pids=' + ','.join(new_fids[:MAX_PERSONS]))
            if data:
                if 'places' in data:
                    for place in data['places']:
                        if place['id'] not in self.places:
                            self.places[place['id']] = (str(place['latitude']), str(place['longitude']))
                loop.run_until_complete(add_datas(loop, data))
                if 'childAndParentsRelationships' in data:
                    for rel in data['childAndParentsRelationships']:
                        father = rel['father']['resourceId'] if 'father' in rel else None
                        mother = rel['mother']['resourceId'] if 'mother' in rel else None
                        child = rel['child']['resourceId'] if 'child' in rel else None
                        if child in self.indi:
                            self.indi[child].parents.add((father, mother))
                        if father in self.indi:
                            self.indi[father].children.add((father, mother, child))
                        if mother in self.indi:
                            self.indi[mother].children.add((father, mother, child))
                if 'relationships' in data:
                    for rel in data['relationships']:
                        if rel['type'] == u'http://gedcomx.org/Couple':
                            person1 = rel['person1']['resourceId']
                            person2 = rel['person2']['resourceId']
                            relfid = rel['id']
                            if person1 in self.indi:
                                self.indi[person1].spouses.add((person1, person2, relfid))
                            if person2 in self.indi:
                                self.indi[person2].spouses.add((person1, person2, relfid))
            new_fids = new_fids[MAX_PERSONS:]

    # add family to the family tree
    def add_fam(self, father, mother):
        if not (father, mother) in self.fam:
            self.fam[(father, mother)] = Fam(father, mother, self)

    # add a children relationship (possibly incomplete) to the family tree
    def add_trio(self, father, mother, child):
        if father in self.indi:
            self.indi[father].add_fams((father, mother))
        if mother in self.indi:
            self.indi[mother].add_fams((father, mother))
        if child in self.indi and (father in self.indi or mother in self.indi):
            self.indi[child].add_famc((father, mother))
            self.add_fam(father, mother)
            self.fam[(father, mother)].add_child(child)

    # add parents relationships
    def add_parents(self, fids):
        parents = set()
        for fid in (fids & self.indi.keys()):
            for couple in self.indi[fid].parents:
                parents |= set(couple)
        if parents:
            self.add_indis(parents)
        for fid in (fids & self.indi.keys()):
            for father, mother in self.indi[fid].parents:
                if mother in self.indi and father in self.indi or not father and mother in self.indi or not mother and father in self.indi:
                    self.add_trio(father, mother, fid)
        return set(filter(None, parents))

    # add spouse relationships
    def add_spouses(self, fids):
        async def add(loop, rels):
            futures = set()
            for father, mother, relfid in rels:
                if (father, mother) in self.fam:
                    futures.add(loop.run_in_executor(None, self.fam[(father, mother)].add_marriage, relfid))
            for future in futures:
                await future

        rels = set()
        for fid in (fids & self.indi.keys()):
            rels |= self.indi[fid].spouses
        loop = asyncio.get_event_loop()
        if rels:
            self.add_indis(set.union(*({father, mother} for father, mother, relfid in rels)))
            for father, mother, relfid in rels:
                if father in self.indi and mother in self.indi:
                    self.indi[father].add_fams((father, mother))
                    self.indi[mother].add_fams((father, mother))
                    self.add_fam(father, mother)
            loop.run_until_complete(add(loop, rels))

    # add children relationships
    def add_children(self, fids):
        rels = set()
        for fid in (fids & self.indi.keys()):
            rels |= self.indi[fid].children if fid in self.indi else set()
        children = set()
        if rels:
            self.add_indis(set.union(*(set(rel) for rel in rels)))
            for father, mother, child in rels:
                if child in self.indi and (mother in self.indi and father in self.indi or not father and mother in self.indi or not mother and father in self.indi):
                    self.add_trio(father, mother, child)
                    children.add(child)
        return children

    # retrieve ordinances
    def add_ordinances(self, fid):
        if fid in self.indi:
            ret, famc = self.indi[fid].get_ordinances()
            if famc and famc in self.fam:
                self.indi[fid].sealing_child.famc = self.fam[famc]
            for o in ret:
                if (fid, o['spouse']['resourceId']) in self.fam:
                    self.fam[(fid, o['spouse']['resourceId'])
                             ].sealing_spouse = Ordinance(o)
                elif (o['spouse']['resourceId'], fid) in self.fam:
                    self.fam[(o['spouse']['resourceId'], fid)
                             ].sealing_spouse = Ordinance(o)

    def reset_num(self):
        for husb, wife in self.fam:
            self.fam[(husb, wife)].husb_num = self.indi[husb].num if husb else None
            self.fam[(husb, wife)].wife_num = self.indi[wife].num if wife else None
            self.fam[(husb, wife)].chil_num = set([self.indi[chil].num for chil in self.fam[(husb, wife)].chil_fid])
        for fid in self.indi:
            self.indi[fid].famc_num = set([self.fam[(husb, wife)].num for husb, wife in self.indi[fid].famc_fid])
            self.indi[fid].fams_num = set([self.fam[(husb, wife)].num for husb, wife in self.indi[fid].fams_fid])

    # print GEDCOM file
    def print(self, file=sys.stdout):
        file.write('0 HEAD\n')
        file.write('1 CHAR UTF-8\n')
        file.write('1 GEDC\n')
        file.write('2 VERS 5.5.1\n')
        file.write('2 FORM LINEAGE-LINKED\n')
        file.write('1 SOUR getmyancestors\n')
        file.write('2 VERS 1.0\n')
        file.write('2 NAME getmyancestors\n')
        file.write('1 DATE ' + time.strftime('%d %b %Y') + '\n')
        file.write('2 TIME ' + time.strftime('%H:%M:%S') + '\n')
        file.write('1 SUBM @SUBM@\n')
        file.write('0 @SUBM@ SUBM\n')
        file.write('1 NAME ' + self.fs.display_name + '\n')
        file.write('1 LANG ' + babelfish.Language.fromalpha2(self.fs.lang).name + '\n')

        for fid in sorted(self.indi, key=lambda x: self.indi.__getitem__(x).num):
            self.indi[fid].print(file)
        for husb, wife in sorted(self.fam, key=lambda x: self.fam.__getitem__(x).num):
            self.fam[(husb, wife)].print(file)
        sources = sorted(self.sources.values(), key=lambda x: x.num)
        for s in sources:
            s.print(file)
        notes = sorted(self.notes, key=lambda x: x.num)
        for i, n in enumerate(notes):
            if i > 0:
                if n.num == notes[i - 1].num:
                    continue
            n.print(file)
        file.write('0 TRLR\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieve GEDCOM data from FamilySearch Tree (4 Jul 2016)', add_help=False, usage='getmyancestors.py -u username -p password [options]')
    parser.add_argument('-u', metavar='<STR>', type=str, help='FamilySearch username')
    parser.add_argument('-p', metavar='<STR>', type=str, help='FamilySearch password')
    parser.add_argument('-i', metavar='<STR>', nargs='+', type=str, help='List of individual FamilySearch IDs for whom to retrieve ancestors')
    parser.add_argument('-a', metavar='<INT>', type=int, default=4, help='Number of generations to ascend [4]')
    parser.add_argument('-d', metavar='<INT>', type=int, default=0, help='Number of generations to descend [0]')
    parser.add_argument('-m', action="store_true", default=False, help='Add spouses and couples information [False]')
    parser.add_argument('-r', action="store_true", default=False, help='Add list of contributors in notes [False]')
    parser.add_argument('-c', action="store_true", default=False, help='Add LDS ordinances (need LDS account) [False]')
    parser.add_argument("-v", action="store_true", default=False, help="Increase output verbosity [False]")
    parser.add_argument('-t', metavar='<INT>', type=int, default=60, help='Timeout in seconds [60]')
    try:
        parser.add_argument('-o', metavar='<FILE>', type=argparse.FileType('w', encoding='UTF-8'), default=sys.stdout, help='output GEDCOM file [stdout]')
        parser.add_argument('-l', metavar='<FILE>', type=argparse.FileType('w', encoding='UTF-8'), default=sys.stderr, help='output log file [stderr]')
    except TypeError:
        sys.stderr.write('Python >= 3.4 is required to run this script\n')
        sys.stderr.write('(see https://docs.python.org/3/whatsnew/3.4.html#argparse)\n')
        exit(2)

    # extract arguments from the command line
    try:
        parser.error = parser.exit
        args = parser.parse_args()
    except SystemExit:
        parser.print_help()
        exit(2)

    if args.i:
        for fid in args.i:
            if not re.match(r'[A-Z0-9]{4}-[A-Z0-9]{3}', fid):
                exit('Invalid FamilySearch ID: ' + fid)

    username = args.u if args.u else input("Enter FamilySearch username: ")
    password = args.p if args.p else getpass.getpass("Enter FamilySearch password: ")

    time_count = time.time()

    # initialize a FamilySearch session and a family tree object
    print('Login to FamilySearch...')
    fs = Session(username, password, args.v, args.l, args.t)
    if not fs.logged:
        exit(2)
    _ = fs._
    tree = Tree(fs)

    # check LDS account
    if args.c and fs.get_url('/platform/tree/persons/%s/ordinances.json' % fs.get_userid()) == 'error':
        exit(2)

    # add list of starting individuals to the family tree
    todo = args.i if args.i else [fs.get_userid()]
    print(_('Downloading starting individuals...'))
    tree.add_indis(todo)

    # download ancestors
    todo = set(todo)
    done = set()
    for i in range(args.a):
        if not todo:
            break
        done |= todo
        print(_('Downloading %s. of generations of ancestors...') % (i + 1))
        todo = tree.add_parents(todo) - done

    # download descendants
    todo = set(tree.indi.keys())
    done = set()
    for i in range(args.d):
        if not todo:
            break
        done |= todo
        print(_('Downloading %s. of generations of descendants...') % (i + 1))
        todo = tree.add_children(todo) - done

    # download spouses
    if args.m:
        print(_('Downloading spouses and marriage information...'))
        todo = set(tree.indi.keys())
        tree.add_spouses(todo)

    # download ordinances, notes and contributors
    async def download_stuff(loop):
        futures = set()
        for fid, indi in tree.indi.items():
            futures.add(loop.run_in_executor(None, indi.get_notes))
            if args.c:
                futures.add(loop.run_in_executor(None, tree.add_ordinances, fid))
            if args.r:
                futures.add(loop.run_in_executor(None, indi.get_contributors))
        for fam in tree.fam.values():
            futures.add(loop.run_in_executor(None, fam.get_notes))
            if args.r:
                futures.add(loop.run_in_executor(None, fam.get_contributors))
        for future in futures:
            await future

    loop = asyncio.get_event_loop()
    print(_('Downloading notes') + (((',' if args.r else _(' and')) + _(' ordinances')) if args.c else '') + (_(' and contributors') if args.r else '') + '...')
    loop.run_until_complete(download_stuff(loop))

    # compute number for family relationships and print GEDCOM file
    tree.reset_num()
    tree.print(args.o)
    print(_('Downloaded %s individuals, %s families, %s sources and %s notes in %s seconds with %s HTTP requests.') % (str(len(tree.indi)), str(len(tree.fam)), str(len(tree.sources)), str(len(tree.notes)), str(round(time.time() - time_count)), str(fs.counter)))
