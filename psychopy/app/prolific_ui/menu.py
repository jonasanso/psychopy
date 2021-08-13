#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

import wx
import requests

from psychopy import logging
from . import ProlificMiniBrowser
from .. import dialogs
from .functions import logInProlific
from psychopy.app.prolific_ui.project import syncProject
from .search import SearchFrame
from .project import ProjectEditor
from psychopy.localization import _translate
from psychopy.projects import prolific


class ProlificMenu(wx.Menu):
    app = None
    appData = None
    currentUser = None
    knownUsers = None
    searchDlg = None

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent  # is a BuilderFrame
        ProlificMenu.app = parent.app
        keys = self.app.keys
        # from prefs fetch info about prev usernames and projects
        ProlificMenu.appData = self.app.prefs.appData['projects']

        # item = self.Append(wx.ID_ANY, _translate("Tell me more..."))
        # parent.Bind(wx.EVT_MENU, self.onAbout, id=item.GetId())

        ProlificMenu.knownUsers = prolific.knownUsers

        # sub-menu for usernames and login
        self.userMenu = wx.Menu()
        # if a user was previously logged in then set them as current
        lastPavUser = ProlificMenu.appData['prolificUser']
        if prolific.knownUsers and (lastPavUser not in prolific.knownUsers):
            lastPavUser = None
        # if lastPavUser and not ProlificMenu.currentUser:
        #     self.setUser(ProlificMenu.appData['prolificUser'])
        for name in self.knownUsers:
            self.addToSubMenu(name, self.userMenu, self.onSetUser)
        self.userMenu.AppendSeparator()
        self.loginBtn = self.userMenu.Append(wx.ID_ANY,
                                    _translate("Log in to Prolific...\t{}")
                                    .format(keys['prolific_logIn']))
        parent.Bind(wx.EVT_MENU, self.onLogInProlific, id=self.loginBtn.GetId())
        self.AppendSubMenu(self.userMenu, _translate("User"))

        # new
        self.newBtn = self.Append(wx.ID_ANY,
                           _translate("New...\t{}").format(keys['projectsNew']))
        parent.Bind(wx.EVT_MENU, self.onNew, id=self.newBtn.GetId())

        self.syncBtn = self.Append(wx.ID_ANY,
                           _translate("Publish\t{}").format(keys['projectsSync']))
        parent.Bind(wx.EVT_MENU, self.onPublish, id=self.syncBtn.GetId())

    def addToSubMenu(self, name, menu, function):
        item = menu.Append(wx.ID_ANY, name)
        self.parent.Bind(wx.EVT_MENU, function, id=item.GetId())

    def onAbout(self, event):
        wx.GetApp().followLink(event)

    def onSetUser(self, event):
        user = self.userMenu.GetLabelText(event.GetId())
        self.setUser(user)

    def setUser(self, user=None):
        if ProlificMenu.appData:
            if user is None and ProlificMenu.appData['prolificUser']:
                user = ProlificMenu.appData['prolificUser']

        if user in [ProlificMenu.currentUser, None]:
            return  # nothing to do here. Move along please.

        ProlificMenu.currentUser = user
        ProlificMenu.appData['prolificUser'] = user
        if user in prolific.knownUsers:
            token = prolific.knownUsers[user]['token']
            try:
                prolific.getCurrentSession().setToken(token)
            except requests.exceptions.ConnectionError:
                logging.warning("Tried to log in to Prolific but no network "
                                "connection")
                return
        else:
            if hasattr(self, 'onLogInProlific'):
                self.onLogInProlific()

        if ProlificMenu.searchDlg:
            ProlificMenu.searchDlg.updateUserProjs()

    def onPublish(self, event):
        prolific.getCurrentSession().publish(self.parent.prolific_project)
        dlg = ProlificMiniBrowser(parent=self.parent, loginOnly=False)
        dlg.setURL(self.parent.prolific_project.submissions_url)
        dlg.ShowModal()

    def onSearch(self, event):
        ProlificMenu.searchDlg = SearchFrame(app=self.parent.app)
        ProlificMenu.searchDlg.Show()

    def onLogInProlific(self, event=None):
        logInProlific(parent=self.parent)

    def onNew(self, event):
        """Create a new project
        """
        if not prolific.getCurrentSession().user.username:
            infoDlg = dialogs.MessageDialog(parent=None, type='Info',
                                            message=_translate(
                                                "You need to log in"
                                                " to create a project"))
            infoDlg.Show()
            return

        if not self.parent.project:
            infoDlg = dialogs.MessageDialog(parent=None, type='Info',
                                            message=_translate(
                                                "You need to activate the project in pavlovia"))
            infoDlg.Show()
            return

        projEditor = ProjectEditor(parent=self.parent)
        if projEditor.ShowModal() == wx.ID_OK:
            self.parent.prolific_project = projEditor.project
            prolific.knownProjects.save()  # update projects.json

