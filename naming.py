#!/usr/bin/env python
"""
'**naming**' is a simple drop-in python library to solve and manage names by
setting configurable rules in the form of a naming convention.

[https://www.github.com/csaez/naming.git](https://www.github.com/csaez/naming.git)
"""

# The MIT License (MIT)
#
# Copyright (c) 2015 Cesar Saez
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# == Helpers & Setup ==
import os
import copy
import json
import logging
from collections import OrderedDict

STR_TYPE = 0
DICT_TYPE = 1
INT_TYPE = 2

FIELDS = dict()
PROFILES = dict()
DB_DRIVER = None
ACTIVE_PROFILE = None


# == User Functions ==

def add_field(name, value, **kwds):
    """Add a `Field` to the naming convention."""
    field = Field(name, value, **kwds)
    FIELDS[name] = field
    return field


def add_profile(name, fields=None, active=False):
    """Add a new `Profile` to the naming convention."""
    profile = Profile(name)
    if fields:
        profile.add_field(fields)
    active = True if not len(PROFILES.keys()) else active
    if active:
        set_active_profile(profile)
    PROFILES[name] = profile
    return profile


def set_active_profile(profile):
    """
    Set the active profile by name, all names will be solved under the rules set
    on this profile/context.
    """
    global ACTIVE_PROFILE  # patch ACTIVE_PROFILE, KISS

    if isinstance(profile, basestring):
        profile = PROFILES.get(profile)

    if profile:
        logging.debug("Setting {} as active profile.".format(profile))
        ACTIVE_PROFILE = profile
        return True
    return False


def active_profile():
    """Get the active profile."""
    global ACTIVE_PROFILE
    if not isinstance(ACTIVE_PROFILE, Profile) or \
            PROFILES.get(ACTIVE_PROFILE.name) is None:
        ACTIVE_PROFILE = None
    return ACTIVE_PROFILE


def save():
    """
    Save all changes to disk in order to make them session persistent (only json
    is supported at the moment, if there's anyone wanting to add support to DB
    drivers please feels free to get in touch).
    """
    if driver() is None:
        set_driver()
    driver().dump(PROFILES=PROFILES, FIELDS=FIELDS,
                  ACTIVE_PROFILE=ACTIVE_PROFILE)


def load():
    """
    Load existing data by using a driver, you should call this function to
    reload the library or init from latest saved state.
    """
    if driver() is None:
        set_driver()
    values = driver().load()
    globals().update(values)


def set_driver(driver=None):
    """
    Set the IO driver to driver, if None is passed it uses the existing active
    driver or init a new one based on json.
    """
    global DB_DRIVER  # KISS

    driver = driver or DB_DRIVER
    if driver is None:
        driver = JSONDriver()

    DB_DRIVER = driver


def driver():
    """
    Return the active I/O driver. It's important to get access through this
    function in order to ensure you are getting the singleton and not
    initializing a new driver on each call.
    """
    return DB_DRIVER


# == Classes ==

class Field(object):
    """This object represent one of the fields/tokens composing the name.

    A name is generally composed by multiple fields, so in order to
    solve/unsolve the final name the library go through each field looking at
    possible answers and pick the best combination possible depending on the
    active `Profile`, allowing the user to skip field values by getting them
    implicitly.

    Fields can be of 3 types (implicitly determined by its value type):

    - `STR_TYPE`: a text field (str/unicode).
    - `DICT_TYPE`: a mapping table (dict).
    - `INT_TYPE`: an integer number (int).
    """

    def __init__(self, name, value, **kwds):
        super(Field, self).__init__()

        self.name = name
        self.value = value
        self.required = kwds.get("required", True)

        {str: self._initStr,
         dict: self._initDict,
         int: self._initInt}.get(type(self.value))(**kwds)

        logging.debug("Init {0} of type {1}".format(
            self, ("STR_TYPE", "DICT_TYPE", "INT_TYPE")[self._type]))

    def _initStr(self, **kwds):
        self._type = STR_TYPE
        self.default = kwds.get("default")

    def _initDict(self, **kwds):
        self._type = DICT_TYPE
        self.default = kwds.get("default", self.value.values()[0])

    def _initInt(self, **kwds):
        self._type = INT_TYPE
        self.padding = kwds.get("padding", 3)
        self.default = str(kwds.get("default", 0)).zfill(self.padding)

    def solve(self, *values):
        """Solve the field by returning a `set` of possible answers."""
        rval = set()  # set of possible values

        for val in values:
            if self._type == STR_TYPE:
                if not isinstance(val, basestring) and self.required:
                    rval.add(val)
            if self._type == DICT_TYPE:
                v = self.value.get(val)
                if v is not None:
                    rval.add(v)
            if self._type == INT_TYPE:
                if type(val) == int:
                    v = str(val).zfill(self.padding)
                    rval.add(v)
            else:
                logging.error("Invalid type: {}".format(val))

        if not len(rval) and self.default:
            rval.add(self.default)

        return rval

    def unsolve(self, *values):
        """Decode a name returning the corresponding mapping."""
        pass


class Profile(object):
    """This object represents a name Profile.

    A Profile groups a set of fields (each one with their own rules) allowing to
    solve/unsolve whole names in different contexts (saving a file to disk,
    naming an instance in a dependency graph and so on).
    """
    def __init__(self, name, fields=None):
        super(Profile, self).__init__()
        self.name = name
        self.fields = OrderedDict()  # order is important!
        self.separator = "_"

        if fields is not None:
            self.add_fields(fields)

    def add_field(self, field):
        """Add a field to this profile."""
        if not isinstance(field, Field):
            logging.error("{} is not a Field".format(field))
            return False
        self.fields[field.name] = field
        return True

    def add_fields(self, fields):
        """Add fields (`iterable`) to this profile."""
        for f in fields:
            self.add_field(f)

    def solve(self, *values):
        """Solve a name based on user input and profile fields."""
        rval = list()
        for name, field in self.fields.iteritems():
            rval.append(name, field.solve(*values))
        return rval

    def unsolve(self, name):
        """Return a `dict` mapping field key values."""
        rval = list()
        values = name.split(self.separator)
        for name, field in self.fields.iteritems():
            rval.append(name, field.unsolve(*values))
        return rval

# === I/O Drivers ===

# Drivers are in charge of managing I/O.


class MemoDriver(object):
    """
    In memory driver, this driver does not save to disk so whatever you set is
    not session persistent (used by unit tests).
    """
    def __init__(self):
        logging.debug("Initializing {}".format(self))

        self.value = dict()
        self.value = self.load()  # update value on init

    def dump(self, **objs):
        logging.debug("Driver saving: {}".format(objs))
        self.value.update(copy.deepcopy(objs))

    def load(self):
        logging.debug("Driver loading: {}".format(self.value))
        return self.value


class JSONDriver(MemoDriver):
    """
    This driver stores to disk by encoding everything as json using python
    builtin json module.
    """
    def dump(self, **objs):
        """
        Dump `objs` as JSON on disk.
        """
        super(JSONDriver, self).dump(**objs)

        if os.path.exists(self.path):
            os.mkdir(self.path)

        for k, v in objs.iteritems():
            with open(os.path.join(self.path, "{}.json".format(k)), "w") as fp:
                json.dump(v, fp)

    def load(self):
        """
        Load and return a data `dict` from disk.
        """
        if not os.path.exists(self.path):
            return

        rval = dict()

        for filename in os.listdir(self.path):
            filepath = os.path.join(self.path, filename)
            if not os.path.isfile(filepath) or not filename.endswith(".json"):
                continue

            with open(filepath) as fp:
                rval[filename.replace(".json", "")] = json.load(fp)

        return rval

    @property
    def path(self):
        """Return the path where naming gets serialized.

        The mechanism follows the order below:

        1. Look at `NAMING_PATH` environment variable.
        2. Look at `~/.local/share/naming.py/`

        > `~` is equvalent to `%userprofile%` on Windows... yay! :)
        """
        home = os.path.expanduser("~")
        naming_path = os.path.join(home, ".local", "share", "naming.py")
        return os.environ.get("NAMING_PATH", naming_path)
