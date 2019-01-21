"""
constants.py - Constant definitions for getmyancestors.

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


def reversed_dict(d):
    """
    Reverse keys/values in dict 'd' such that value->key/key->value.

    Arguments:
        d {dict} -- Python dict.

    Returns:
        [dict] -- Python dict with keys and values in dict 'd' reversed.

    """
    return {val: key for key, val in d.items()}


# MAX_PERSONS is subject to change.
# See https://www.familysearch.org/developers/docs/api/tree/Persons_resource
MAX_PERSONS = 200

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

FACT_TYPES = reversed_dict(FACT_TAGS)
ORDINANCES = reversed_dict(ORDINANCES_STATUS)
