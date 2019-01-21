# -*- coding: utf-8 -*-
"""
shared_classes.py - Classes used by getmyancestors.

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

import sys
import time
import asyncio
import re

try:
    import requests
except ImportError:
    sys.stderr.write('You need to install the requests module first.\n')
    sys.stderr.write('In your terminal, run:\n')
    sys.stderr.write('python3 -m pip install requests\n')
    sys.stderr.write('or:\n')
    sys.stderr.write('python3 -m pip install --user requests')
    exit(2)

# Local imports.
from constants import (
    FACT_TAGS, FACT_EVEN, ORDINANCES_STATUS, FACT_TYPES, ORDINANCES,
    MAX_PERSONS)
from translation import translations


def cont(string):
    """
    [summary].

    Arguments:
        string {str} -- [description]

    Returns:
        [str] -- [description]

    """
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


# FamilySearch session class.
class Session:
    """
    [summary].

    Returns:
        [type] -- [description]

    """

    def __init__(self, username, password, verbose=False, logfile=sys.stderr, timeout=60):
        """
        [summary].

        Arguments:
            username {[type]} -- [description]
            password {[type]} -- [description]

        Keyword Arguments:
            verbose {bool} -- [description] (default: {False})
            logfile {[type]} -- [description] (default: {sys.stderr})
            timeout {int} -- [description] (default: {60})
        """
        self.username = username
        self.password = password
        self.verbose = verbose
        self.logfile = logfile
        self.timeout = timeout
        self.fid = self.lang = None
        self.counter = 0
        self.logged = self.login()

    # Write in logfile if verbose enabled.
    def write_log(self, text):
        """
        [summary].

        Arguments:
            text {[type]} -- [description]
        """
        if self.verbose:
            self.logfile.write('[%s]: %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), text))

    # Retrieve FamilySearch session ID.
    # (https://familysearch.org/developers/docs/guides/oauth2)
    def login(self):
        """
        [summary].

        Returns:
            [type] -- [description]

        """
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

    # Retrieve JSON structure from FamilySearch URL.
    def get_url(self, url):
        """
        [summary].

        Arguments:
            url {[type]} -- [description]

        Returns:
            [type] -- [description]

        """
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

    # Retrieve FamilySearch current user ID.
    def set_current(self):
        """[summary]."""
        url = '/platform/users/current.json'
        data = self.get_url(url)
        if data:
            self.fid = data['users'][0]['personId']
            self.lang = data['users'][0]['preferredLanguage']

    def get_userid(self):
        """
        [summary].

        Returns:
            [type] -- [description]

        """
        if not self.fid:
            self.set_current()
        return self.fid

    def _(self, string):
        if not self.lang:
            self.set_current()
        if string in translations and self.lang in translations[string]:
            return translations[string][self.lang]
        return string


# Some GEDCOM objects.
class Note:
    """[summary]."""

    counter = 0

    def __init__(self, text='', tree=None, num=None):
        """
        [summary].

        Keyword Arguments:
            text {str} -- [description] (default: {''})
            tree {[type]} -- [description] (default: {None})
            num {[type]} -- [description] (default: {None})
        """
        if num:
            self.num = num
        else:
            Note.counter += 1
            self.num = Note.counter
        self.text = text.strip()

        if tree:
            tree.notes.append(self)

    def print(self, file=sys.stdout):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
        file.write(cont('0 @N' + str(self.num) + '@ NOTE ' + self.text) + '\n')

    def link(self, file=sys.stdout, level=1):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
            level {int} -- [description] (default: {1})
        """
        file.write(str(level) + ' NOTE @N' + str(self.num) + '@\n')


class Source:
    """[summary]."""

    counter = 0

    def __init__(self, data=None, tree=None, num=None):
        """
        [summary].

        Keyword Arguments:
            data {[type]} -- [description] (default: {None})
            tree {[type]} -- [description] (default: {None})
            num {[type]} -- [description] (default: {None})
        """
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
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
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
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
            level {int} -- [description] (default: {1})
        """
        file.write(str(level) + ' SOUR @S' + str(self.num) + '@\n')


class Fact:
    """[summary]."""

    def __init__(self, data=None, tree=None):
        """
        [summary].

        Keyword Arguments:
            data {[type]} -- [description] (default: {None})
            tree {[type]} -- [description] (default: {None})
        """
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
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
            key {[type]} -- [description] (default: {None})
        """
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
    """[summary]."""

    def __init__(self, data=None):
        """
        [summary].

        Keyword Arguments:
            data {[type]} -- [description] (default: {None})
        """
        self.description = self.url = None
        if data and 'links' in data:
            self.url = data['about']
            if 'titles' in data:
                self.description = data['titles'][0]['value']
            if 'descriptions' in data:
                self.description = ('' if not self.description else self.description + '\n') + data['descriptions'][0]['value']

    def print(self, file=sys.stdout):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
        file.write('1 OBJE\n2 FORM URL\n')
        if self.description:
            file.write(cont('2 TITL ' + self.description) + '\n')
        if self.url:
            file.write(cont('2 FILE ' + self.url) + '\n')


class Name:
    """[summary]."""

    def __init__(self, data=None, tree=None):
        """
        [summary].

        Keyword Arguments:
            data {[type]} -- [description] (default: {None})
            tree {[type]} -- [description] (default: {None})
        """
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
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
            typ {[type]} -- [description] (default: {None})
        """
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
    """[summary]."""

    def __init__(self, data=None):
        """
        [summary].

        Keyword Arguments:
            data {[type]} -- [description] (default: {None})
        """
        self.date = self.temple_code = self.status = self.famc = None
        if data:
            if 'date' in data:
                self.date = data['date']['formal']
            if 'templeCode' in data:
                self.temple_code = data['templeCode']
            self.status = data['status']

    def print(self, file=sys.stdout):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
        if self.date:
            file.write(cont('2 DATE ' + self.date) + '\n')
        if self.temple_code:
            file.write('2 TEMP ' + self.temple_code + '\n')
        if self.status in ORDINANCES_STATUS:
            file.write('2 STAT ' + ORDINANCES_STATUS[self.status] + '\n')
        if self.famc:
            file.write('2 FAMC @F' + str(self.famc.num) + '@\n')


# GEDCOM individual class.
class Indi:
    """
    [summary].

    Returns:
        [type] -- [description]

    """

    counter = 0

    # Initialize individual.
    def __init__(self, fid=None, tree=None, num=None):
        """
        [summary].

        Keyword Arguments:
            fid {[type]} -- [description] (default: {None})
            tree {[type]} -- [description] (default: {None})
            num {[type]} -- [description] (default: {None})
        """
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
        """
        [summary].

        Arguments:
            data {[type]} -- [description]
        """
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

    # Add a fams to the individual.
    def add_fams(self, fams):
        """
        [summary].

        Arguments:
            fams {[type]} -- [description]
        """
        self.fams_fid.add(fams)

    # Add a famc to the individual.
    def add_famc(self, famc):
        """
        [summary].

        Arguments:
            famc {[type]} -- [description]
        """
        self.famc_fid.add(famc)

    # Retrieve individual notes.
    def get_notes(self):
        """[summary]."""
        notes = self.tree.fs.get_url('/platform/tree/persons/%s/notes.json' % self.fid)
        if notes:
            for n in notes['persons'][0]['notes']:
                text_note = '=== ' + n['subject'] + ' ===\n' if 'subject' in n else ''
                text_note += n['text'] + '\n' if 'text' in n else ''
                self.notes.add(Note(text_note, self.tree))

    # Retrieve LDS ordinances.
    def get_ordinances(self):
        """
        [summary].

        Returns:
            [type] -- [description]

        """
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

    # Retrieve contributors.
    def get_contributors(self):
        """[summary]."""
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

    # Print individual information in GEDCOM format.
    def print(self, file=sys.stdout):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
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


# GEDCOM family class.
class Fam:
    """[summary]."""

    counter = 0

    # Initialize family.
    def __init__(self, husb=None, wife=None, tree=None, num=None):
        """
        [summary].

        Keyword Arguments:
            husb {[type]} -- [description] (default: {None})
            wife {[type]} -- [description] (default: {None})
            tree {[type]} -- [description] (default: {None})
            num {[type]} -- [description] (default: {None})
        """
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

    # Add a child to the family.
    def add_child(self, child):
        """
        [summary].

        Arguments:
            child {[type]} -- [description]
        """
        if child not in self.chil_fid:
            self.chil_fid.add(child)

    # Retrieve and add marriage information.
    def add_marriage(self, fid):
        """
        [summary].

        Arguments:
            fid {[type]} -- [description]
        """
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

    # Retrieve marriage notes.
    def get_notes(self):
        """[summary]."""
        if self.fid:
            notes = self.tree.fs.get_url('/platform/tree/couple-relationships/%s/notes.json' % self.fid)
            if notes:
                for n in notes['relationships'][0]['notes']:
                    text_note = '=== ' + n['subject'] + ' ===\n' if 'subject' in n else ''
                    text_note += n['text'] + '\n' if 'text' in n else ''
                    self.notes.add(Note(text_note, self.tree))

    # Retrieve contributors.
    def get_contributors(self):
        """[summary]."""
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

    # Print family information in GEDCOM format.
    def print(self, file=sys.stdout):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
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


# Family tree class.
class Tree:
    """
    [summary].

    Returns:
        [type] -- [description]

    """

    def __init__(self, fs=None):
        """
        [summary].

        Keyword Arguments:
            fs {[type]} -- [description] (default: {None})
        """
        self.fs = fs
        self.indi = dict()
        self.fam = dict()
        self.notes = list()
        self.sources = dict()
        self.places = dict()

    # Add individuals to the family tree.
    def add_indis(self, fids):
        """
        [summary].

        Arguments:
            fids {[type]} -- [description]
        """
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

    # Add family to the family tree.
    def add_fam(self, father, mother):
        """
        [summary].

        Arguments:
            father {[type]} -- [description]
            mother {[type]} -- [description]
        """
        if not (father, mother) in self.fam:
            self.fam[(father, mother)] = Fam(father, mother, self)

    # Add a children relationship (possibly incomplete) to the family tree.
    def add_trio(self, father, mother, child):
        """
        [summary].

        Arguments:
            father {[type]} -- [description]
            mother {[type]} -- [description]
            child {[type]} -- [description]
        """
        if father in self.indi:
            self.indi[father].add_fams((father, mother))
        if mother in self.indi:
            self.indi[mother].add_fams((father, mother))
        if child in self.indi and (father in self.indi or mother in self.indi):
            self.indi[child].add_famc((father, mother))
            self.add_fam(father, mother)
            self.fam[(father, mother)].add_child(child)

    # Add parents relationships.
    def add_parents(self, fids):
        """
        [summary].

        Arguments:
            fids {[type]} -- [description]

        Returns:
            [type] -- [description]

        """
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

    # Add spouse relationships.
    def add_spouses(self, fids):
        """
        [summary].

        Arguments:
            fids {[type]} -- [description]
        """
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

    # Add children relationships.
    def add_children(self, fids):
        """
        [summary].

        Arguments:
            fids {[type]} -- [description]

        Returns:
            [type] -- [description]

        """
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

    # Retrieve ordinances.
    def add_ordinances(self, fid):
        """
        [summary].

        Arguments:
            fid {[type]} -- [description]
        """
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
        """[summary]."""
        for husb, wife in self.fam:
            self.fam[(husb, wife)].husb_num = self.indi[husb].num if husb else None
            self.fam[(husb, wife)].wife_num = self.indi[wife].num if wife else None
            self.fam[(husb, wife)].chil_num = set([self.indi[chil].num for chil in self.fam[(husb, wife)].chil_fid])
        for fid in self.indi:
            self.indi[fid].famc_num = set([self.fam[(husb, wife)].num for husb, wife in self.indi[fid].famc_fid])
            self.indi[fid].fams_num = set([self.fam[(husb, wife)].num for husb, wife in self.indi[fid].fams_fid])

    # Print GEDCOM file.
    def print(self, file=sys.stdout):
        """
        [summary].

        Keyword Arguments:
            file {[type]} -- [description] (default: {sys.stdout})
        """
        file.write('0 HEAD\n')
        file.write('1 CHAR UTF-8\n')
        file.write('1 GEDC\n')
        file.write('2 VERS 5.5\n')
        file.write('2 FORM LINEAGE-LINKED\n')
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


class Gedcom:
    """
    [summary].

    Returns:
        [type] -- [description]

    """

    def __init__(self, file, tree):
        """
        [summary].

        Arguments:
            file {[type]} -- [description]
            tree {[type]} -- [description]
        """
        self.f = file
        self.num = None
        self.tree = tree
        self.level = 0
        self.pointer = None
        self.tag = None
        self.data = None
        self.flag = False
        self.indi = dict()
        self.fam = dict()
        self.note = dict()
        self.sour = dict()
        self.__parse()
        self.__add_id()

    def __parse(self):
        while self.__get_line():
            if self.tag == 'INDI':
                self.num = int(self.pointer[2:len(self.pointer) - 1])
                self.indi[self.num] = Indi(tree=self.tree, num=self.num)
                self.__get_indi()
            elif self.tag == 'FAM':
                self.num = int(self.pointer[2:len(self.pointer) - 1])
                if self.num not in self.fam:
                    self.fam[self.num] = Fam(tree=self.tree, num=self.num)
                self.__get_fam()
            elif self.tag == 'NOTE':
                self.num = int(self.pointer[2:len(self.pointer) - 1])
                if self.num not in self.note:
                    self.note[self.num] = Note(tree=self.tree, num=self.num)
                self.__get_note()
            elif self.tag == 'SOUR':
                self.num = int(self.pointer[2:len(self.pointer) - 1])
                if self.num not in self.sour:
                    self.sour[self.num] = Source(num=self.num)
                self.__get_source()
            else:
                continue

    def __get_line(self):
        # If the flag is set, skip reading a newline.
        if self.flag:
            self.flag = False
            return True
        words = self.f.readline().split()

        if not words:
            return False
        self.level = int(words[0])
        if words[1][0] == '@':
            self.pointer = words[1]
            self.tag = words[2]
            self.data = ' '.join(words[3:])
        else:
            self.pointer = None
            self.tag = words[1]
            self.data = ' '.join(words[2:])
        return True

    def __get_indi(self):
        while self.f and self.__get_line() and self.level > 0:
            if self.tag == 'NAME':
                self.__get_name()
            elif self.tag == 'SEX':
                self.indi[self.num].gender = self.data
            elif self.tag in FACT_TYPES or self.tag == 'EVEN':
                self.indi[self.num].facts.add(self.__get_fact())
            elif self.tag == 'BAPL':
                self.indi[self.num].baptism = self.__get_ordinance()
            elif self.tag == 'CONL':
                self.indi[self.num].confirmation = self.__get_ordinance()
            elif self.tag == 'ENDL':
                self.indi[self.num].endowment = self.__get_ordinance()
            elif self.tag == 'SLGC':
                self.indi[self.num].sealing_child = self.__get_ordinance()
            elif self.tag == 'FAMS':
                self.indi[self.num].fams_num.add(int(self.data[2:len(self.data) - 1]))
            elif self.tag == 'FAMC':
                self.indi[self.num].famc_num.add(int(self.data[2:len(self.data) - 1]))
            elif self.tag == '_FSFTID':
                self.indi[self.num].fid = self.data
            elif self.tag == 'NOTE':
                num = int(self.data[2:len(self.data) - 1])
                if num not in self.note:
                    self.note[num] = Note(tree=self.tree, num=num)
                self.indi[self.num].notes.add(self.note[num])
            elif self.tag == 'SOUR':
                self.indi[self.num].sources.add(self.__get_link_source())
            elif self.tag == 'OBJE':
                self.indi[self.num].memories.add(self.__get_memorie())
        self.flag = True

    def __get_fam(self):
        while self.__get_line() and self.level > 0:
            if self.tag == 'HUSB':
                self.fam[self.num].husb_num = int(self.data[2:len(self.data) - 1])
            elif self.tag == 'WIFE':
                self.fam[self.num].wife_num = int(self.data[2:len(self.data) - 1])
            elif self.tag == 'CHIL':
                self.fam[self.num].chil_num.add(int(self.data[2:len(self.data) - 1]))
            elif self.tag in FACT_TYPES:
                self.fam[self.num].facts.add(self.__get_fact())
            elif self.tag == 'SLGS':
                self.fam[self.num].sealing_spouse = self.__get_ordinance()
            elif self.tag == '_FSFTID':
                self.fam[self.num].fid = self.data
            elif self.tag == 'NOTE':
                num = int(self.data[2:len(self.data) - 1])
                if num not in self.note:
                    self.note[num] = Note(tree=self.tree, num=num)
                self.fam[self.num].notes.add(self.note[num])
            elif self.tag == 'SOUR':
                self.fam[self.num].sources.add(self.__get_link_source())
        self.flag = True

    def __get_name(self):
        parts = self.__get_text().split('/')
        name = Name()
        added = False
        name.given = parts[0].strip()
        name.surname = parts[1].strip()
        if parts[2]:
            name.suffix = parts[2]
        if not self.indi[self.num].name:
            self.indi[self.num].name = name
            added = True
        while self.__get_line() and self.level > 1:
            if self.tag == 'NPFX':
                name.prefix = self.data
            elif self.tag == 'TYPE':
                if self.data == 'aka':
                    self.indi[self.num].aka.add(name)
                    added = True
                elif self.data == 'married':
                    self.indi[self.num].married.add(name)
                    added = True
            elif self.tag == 'NICK':
                nick = Name()
                nick.given = self.data
                self.indi[self.num].nicknames.add(nick)
            elif self.tag == 'NOTE':
                num = int(self.data[2:len(self.data) - 1])
                if num not in self.note:
                    self.note[num] = Note(tree=self.tree, num=num)
                name.note = self.note[num]
        if not added:
            self.indi[self.num].birthnames.add(name)
        self.flag = True

    def __get_fact(self):
        fact = Fact()
        if self.tag != 'EVEN':
            fact.type = FACT_TYPES[self.tag]
            fact.value = self.data
        while self.__get_line() and self.level > 1:
            if self.tag == 'TYPE':
                fact.type = self.data
            if self.tag == 'DATE':
                fact.date = self.__get_text()
            elif self.tag == 'PLAC':
                fact.place = self.__get_text()
            elif self.tag == 'MAP':
                fact.map = self.__get_map()
            elif self.tag == 'NOTE':
                if self.data[:12] == 'Description:':
                    fact.value = self.data[13:]
                    continue
                num = int(self.data[2:len(self.data) - 1])
                if num not in self.note:
                    self.note[num] = Note(tree=self.tree, num=num)
                fact.note = self.note[num]
            elif self.tag == 'CONT':
                fact.value += '\n' + self.data
            elif self.tag == 'CONC':
                fact.value += self.data
        self.flag = True
        return fact

    def __get_map(self):
        latitude = None
        longitude = None
        while self.__get_line() and self.level > 3:
            if self.tag == 'LATI':
                latitude = self.data
            elif self.tag == 'LONG':
                longitude = self.data
        self.flag = True
        return (latitude, longitude)

    def __get_text(self):
        text = self.data
        while self.__get_line():
            if self.tag == 'CONT':
                text += '\n' + self.data
            elif self.tag == 'CONC':
                text += self.data
            else:
                break
        self.flag = True
        return text

    def __get_source(self):
        while self.__get_line() and self.level > 0:
            if self.tag == 'TITL':
                self.sour[self.num].title = self.__get_text()
            elif self.tag == 'AUTH':
                self.sour[self.num].citation = self.__get_text()
            elif self.tag == 'PUBL':
                self.sour[self.num].url = self.__get_text()
            elif self.tag == 'REFN':
                self.sour[self.num].fid = self.data
                if self.data in self.tree.sources:
                    self.sour[self.num] = self.tree.sources[self.data]
                else:
                    self.tree.sources[self.data] = self.sour[self.num]
            elif self.tag == 'NOTE':
                num = int(self.data[2:len(self.data) - 1])
                if num not in self.note:
                    self.note[num] = Note(tree=self.tree, num=num)
                self.sour[self.num].notes.add(self.note[num])
        self.flag = True

    def __get_link_source(self):
        num = int(self.data[2:len(self.data) - 1])
        if num not in self.sour:
            self.sour[num] = Source(num=num)
        page = None
        while self.__get_line() and self.level > 1:
            if self.tag == 'PAGE':
                page = self.__get_text()
        self.flag = True
        return (self.sour[num], page)

    def __get_memorie(self):
        memorie = Memorie()
        while self.__get_line() and self.level > 1:
            if self.tag == 'TITL':
                memorie.description = self.__get_text()
            elif self.tag == 'FILE':
                memorie.url = self.__get_text()
        self.flag = True
        return memorie

    def __get_note(self):
        self.note[self.num].text = self.__get_text()
        self.flag = True

    def __get_ordinance(self):
        ordinance = Ordinance()
        while self.__get_line() and self.level > 1:
            if self.tag == 'DATE':
                ordinance.date = self.__get_text()
            elif self.tag == 'TEMP':
                ordinance.temple_code = self.data
            elif self.tag == 'STAT':
                ordinance.status = ORDINANCES[self.data]
            elif self.tag == 'FAMC':
                num = int(self.data[2:len(self.data) - 1])
                if num not in self.fam:
                    self.fam[num] = Fam(tree=self.tree, num=num)
                ordinance.famc = self.fam[num]
        self.flag = True
        return ordinance

    def __add_id(self):
        for num in self.fam:
            if self.fam[num].husb_num:
                self.fam[num].husb_fid = self.indi[self.fam[num].husb_num].fid
            if self.fam[num].wife_num:
                self.fam[num].wife_fid = self.indi[self.fam[num].wife_num].fid
            for chil in self.fam[num].chil_num:
                self.fam[num].chil_fid.add(self.indi[chil].fid)
        for num in self.indi:
            for famc in self.indi[num].famc_num:
                self.indi[num].famc_fid.add((self.fam[famc].husb_fid, self.fam[famc].wife_fid))
            for fams in self.indi[num].fams_num:
                self.indi[num].fams_fid.add((self.fam[fams].husb_fid, self.fam[fams].wife_fid))
