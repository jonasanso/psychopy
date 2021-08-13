#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""Helper functions in PsychoPy for interacting with prolific.co
"""
from future.builtins import object
import glob
import pathlib
import os, time, socket
import subprocess
import traceback
from pkg_resources import parse_version

from psychopy import logging, prefs, constants, exceptions
from psychopy.tools.filetools import DictStorage, KnownProjects
from psychopy import app
from psychopy.localization import _translate
from .prolific_client import ProlificClient

try:
    import git  # must import psychopy constants before this (custom git path)
    haveGit = True
except ImportError:
    haveGit = False

import requests
import gitlab
import gitlab.v4.objects

# for authentication
from . import sshkeys, prolific_client
from uuid import uuid4

from .gitignore import gitIgnoreText

if constants.PY3:
    from urllib import parse

    urlencode = parse.quote
else:
    import urllib

    urlencode = urllib.quote


# TODO: test what happens if we have a network initially but lose it
# TODO: test what happens if we have a network but prolific times out

prolificPrefsDir = os.path.join(prefs.paths['userPrefsDir'], 'prolific')
rootURL = "https://test-client.prolific.co/"
client_id = '4bb79f0356a566cd7b49e3130c714d9140f1d3de4ff27c7583fb34fbfac604e0'
scopes = []
redirect_url = 'https://test-client.prolific.co/'

knownUsers = DictStorage(
        filename=os.path.join(prolificPrefsDir, 'users.json'))

# knownProjects is a dict stored by id ("namespace/name")
knownProjects = KnownProjects(
        filename=os.path.join(prolificPrefsDir, 'projects.json'))

permissions = {  # for ref see https://docs.gitlab.com/ee/user/permissions.html
    'guest': 10,
    'reporter': 20,
    'developer': 30,  # (can push to non-protected branches)
    'maintainer': 30,
    'owner': 50}

MISSING_REMOTE = -1
OK = 1


def getAuthURL():
    state = str(uuid4())  # create a private "state" based on uuid
    auth_url = "https://test.prolific.co/auth/accounts/login/"
    return auth_url, state


def login(tokenOrUsername, rememberMe=True):
    """Sets the current user by means of a token

    Parameters
    ----------
    token
    """
    currentSession = getCurrentSession()
    if not currentSession:
        raise requests.exceptions.ConnectionError("Failed to connect to prolific.co. No network?")
    # would be nice here to test whether this is a token or username
    logging.debug('prolificTokensCurrently: {}'.format(knownUsers))
    if tokenOrUsername in knownUsers:
        token = knownUsers[tokenOrUsername]  # username so fetch token
    else:
        token = tokenOrUsername
    # it might still be a dict that *contains* the token
    if type(token) == dict and 'token' in token:
        token = token['token']

    # try actually logging in with token
    currentSession.setToken(token)
    user = currentSession.user
    prefs.appData['projects']['prolificUser'] = user.username


def logout():
    """Log the current user out of prolific.

    NB This function does not delete the cookie from the wx mini-browser
    if that has been set. Use prolific_ui for that.

     - set the user for the currentSession to None
     - save the appData so that the user is blank
    """
    # create a new currentSession with no auth token
    global _existingSession
    _existingSession = ProlificSession()  # create an empty session (user is None)
    # set appData to None
    prefs.appData['projects']['prolificUser'] = None
    prefs.saveAppData()
    for frameWeakref in app.openFrames:
        frame = frameWeakref()
        if hasattr(frame, 'setUser'):
            frame.setUser(None)


class User(object):
    """Class to combine what we know about the user locally and on gitlab

    (from previous logins and from the current session)"""

    def __init__(self, localData, rememberMe=True):
        self.data = localData
        self.data['token'] = getCurrentSession().getToken()

        if rememberMe:
            self.saveLocal()

    def __str__(self):
        return "prolific.User <{}>".format(self.username)

    @property
    def id(self):
        if 'id' in self.data:
            return self.data['id']
        else:
            return None

    @property
    def username(self):
        if 'username' in self.data:
            return self.data['username']
        else:
            return None

    @property
    def currency_symbol(self):
        if self.currency_code:
            return currency_symbol[self.currency_code]
        else:
            return None

    @property
    def currency_code(self):
        if 'currency_code' in self.data:
            return self.data['currency_code']
        else:
            return None

    @property
    def url(self):
        return "https://test-client.prolific.co/account/general"

    @property
    def name(self):
        return self.data.get('name')

    @name.setter
    def name(self, name):
        self.data['name'] = name

    @property
    def token(self):
        return self.data['token']

    @property
    def avatar(self):
        if 'avatar' in self.data:
            return self.data['avatar']
        else:
            return None

    @avatar.setter
    def avatar(self, location):
        if os.path.isfile(location):
            self.data['avatar'] = location

    def saveLocal(self):
        """Saves the data on the current user in the prolific/users json file"""
        # update stored tokens
        tokens = knownUsers
        tokens[self.username] = self.data
        tokens.save()

    def save(self):
        self.saveLocal()


class ProlificSession:
    """A class to track a session with the server.

    The session will store a token, which can then be used to authenticate
    for project read/write access
    """

    def __init__(self, token=None, remember_me=True):
        """Create a session to send requests with the prolific server

        Provide either username and password for authentication with a new
        token, or provide a token from a previous session, or nothing for an
        anonymous user
        """
        self.username = None
        self.userID = None  # populate when token property is set
        self.userFullName = None
        self.remember_me = remember_me
        self.authenticated = False
        self.currentProject = None
        self.setToken(token)
        logging.debug("ProlificLoggedIn")

    def calculate_total_price(self, participants, reward):
        if self.client:
            total = self.client.calculate_total(participants, reward)
            return f"{total}{self.user.currency_symbol}"
        return ""

    def createProject(self, pavloviaId, title, internal_name, description, url, code, participants, duration, reward):
        """
        Returns
        -------
        a ProlificProject object

        """
        study = self.client.create_study(title, internal_name, description, url, code, participants, duration, reward)
        if study:
            return ProlificProject(pavloviaId, study)
        return None

    def publish(self, project):
        study = self.client.publish_study(project.idNumber)
        if study:
            return ProlificProject(project.pavloviaId, study)


    def getProject(self, id, repo=None):
        """Gets a Prolific project from an ID number or namespace/name

        Parameters
        ----------
        id a numerical

        Returns
        -------
        prolific.ProlificProject or None

        """
        if id:
            return ProlificProject(id, repo=repo)
        elif repo:
            return ProlificProject(repo=repo)
        else:
            return None

    def findProjects(self, search_str='', tags="psychopy"):
        """
        Parameters
        ----------
        search_str : str
            The string to search for in the title of the project
        tags : str
            Comma-separated string containing tags

        Returns
        -------
        A list of OSFProject objects

        """
        rawProjs = self.gitlab.projects.list(
                search=search_str,
                as_list=False)  # iterator not list for auto-pagination
        projs = [ProlificProject(proj) for proj in rawProjs if proj.id]
        return projs

    def findUserProjects(self, searchStr=''):
        """Finds all readable projects of a given user_id
        (None for current user)
        """
        try:
            own = self.client.projects.list(owned=True, search=searchStr)
        except Exception as e:
            print(e)
            own = self.client.projects.list(owned=True, search=searchStr)
        group = self.client.projects.list(owned=False, membership=True,
                                          search=searchStr)
        projs = []
        projIDs = []
        for proj in own + group:
            if proj.id not in projIDs and proj.id not in projs:
                projs.append(ProlificProject(proj))
                projIDs.append(proj.id)
        return projs

    def findUsers(self, search_str):
        """Find user IDs whose name matches a given search string
        """
        return self.gitlab.users

    def getToken(self):
        """The authorisation token for the current logged in user
        """
        return self.__dict__['token']

    def setToken(self, token):
        """Set the token for this session and check that it works for auth
        """
        self.__dict__['token'] = token
        self.startSession()

    def getNamespace(self, namespace):
        """Returns a namespace object for the given name if an exact match is
        found
        """
        spaces = self.gitlab.namespaces.list(search=namespace)
        # might be more than one, with
        for thisSpace in spaces:
            if thisSpace.path == namespace:
                return thisSpace

    def startSession(self):
        """Start a gitlab session as best we can
        (if no token then start an empty session)"""
        if not self.client:
            self.authenticated = False
            return

        user = self.user

        self.username = user.username
        self.userID = user.id
        self.userFullName = user.name
        self.authenticated = True


    @property
    def client(self):
        if self.getToken():
            return ProlificClient(self.getToken())
        else:
            return None

    @property
    def user(self):
        if self.client:
            user = self.client.retrieve_prolific_user()
            if user:
                return User(localData=user)
        
        return User(localData={}, rememberMe=False)


class ProlificProject(dict):
    """A Prolific project, with name, url etc
    """

    def __init__(self, pavloviaId, data):
        dict.__init__(self)
        self._storedAttribs = {}  # these will go into knownProjects file
        self.pavloviaId = pavloviaId
        self.prolific = data
        self['id'] = pavloviaId
        self['idNumber'] = data['id']
        self['title'] = data['name']
        self['url'] = ''

        self._lastKnownSync = 0

    def __getattr__(self, name):
        proj = self.__dict__['prolific']
        if not proj:
            return
        toSearch = [self, self.__dict__, proj]
        for attDict in toSearch:
            if name in attDict:
                return attDict[name]
        # error if none found
        if name == 'id':
            selfDescr = "ProlificProject"
        else:
            selfDescr = repr(
                    self)  # this includes self.id so don't use if id fails!
        raise AttributeError("No attribute '{}' in {}".format(name, selfDescr))


    @property
    def id(self):
        return self.pavloviaId

    @property
    def idNumber(self):
        if self.prolific:
            return self.prolific.get('id')

    @property
    def title(self):
        """The title of this project (alias for name)
        """
        return self.prolific.get("name")


    @property
    def url(self):
        """The title of this project (alias for name)
        """
        return self.prolific.get("url")

    @property
    def submissions_url(self):
        """The title of this project (alias for name)
        """
        return self.prolific.get("url") + "submissions/"

    def sync(self, infoStream=None):
        return 1

    def save(self):
        pass

    @property
    def prolificStatus(self):
        return self.__dict__['status']

    @prolificStatus.setter
    def prolificStatus(self, newStatus):
        raise Exception("Transition here")
        url = 'https://prolific.co/server?command=update_project'
        data = {'projectId': self.idNumber, 'projectStatus': 'ACTIVATED'}
        resp = requests.put(url, data)
        if resp.status_code == 200:
            self.__dict__['prolificStatus'] = newStatus
        else:
            print(resp)



def getGitRoot(p):
    """Return None or the root path of the repository"""
    if not haveGit:
        raise exceptions.DependencyError(
                "gitpython and a git installation required for getGitRoot()")

    p = pathlib.Path(p).absolute()
    if not p.is_dir():
        p = p.parent  # given a file instead of folder?

    proc = subprocess.Popen('git branch --show-current',
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=str(p), shell=True,
                            universal_newlines=True)  # newlines forces stdout to unicode
    stdout, stderr = proc.communicate()
    if 'not a git repository' in (stdout + stderr):
        return None
    else:
        # this should have been possible with git rev-parse --top-level
        # but that sometimes returns a virtual symlink that is not the normal folder name
        # e.g. some other mount point?
        selfAndParents = [p] + list(p.parents)
        for thisPath in selfAndParents:
            if list(thisPath.glob('.git')):
                return str(thisPath)  # convert Path back to str


def getProject(filename):
    """Will try to find (locally synced) prolific Project for the filename
    """
    raise Exception("not implemented")

global _existingSession
_existingSession = None


# create an instance of that
def getCurrentSession():
    """Returns the current Prolific session, creating one if not yet present

    Returns
    -------

    """
    global _existingSession
    if _existingSession:
        return _existingSession
    else:
        _existingSession = ProlificSession()
    refreshSession()
    return _existingSession


def refreshSession():
    """Restarts the session with the same user logged in"""
    global _existingSession
    if _existingSession and _existingSession.getToken():
        _existingSession = ProlificSession(
                token=_existingSession.getToken()
        )
    else:
        _existingSession = ProlificSession()
    return _existingSession



currency_symbol = {
    "GBP": "£",
    "USD": "$"
}
