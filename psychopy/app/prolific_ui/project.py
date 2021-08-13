#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019-2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).
import sys
import time
import os
import traceback
from decimal import Decimal

from .functions import (setLocalPath, showCommitDialog, logInProlific,
                        noGitWarning)
from psychopy.localization import _translate
from psychopy.projects import prolific
from psychopy import logging

from psychopy.app.prolific_ui import sync

import wx
from wx.lib import scrolledpanel as scrlpanel

try:
    import wx.lib.agw.hyperlink as wxhl  # 4.0+
except ImportError:
    import wx.lib.hyperlink as wxhl  # <3.0.2


class ProjectEditor(wx.Dialog):
    def __init__(self, parent=None, id=wx.ID_ANY, project=None,
                 *args, **kwargs):

        wx.Dialog.__init__(self, parent, id,
                           *args, **kwargs)
        panel = wx.Panel(self, wx.ID_ANY, style=wx.TAB_TRAVERSAL)
        # when a project is successfully created these will be populated
        self.pavloviaId = parent.project.id
        self.project = project  # type: prolific.ProlificProject
        self.projInfo = None
        self.parent = parent

        if project:
            # edit existing project
            self.isNew = False
        else:
            self.isNew = True

        # create the controls
        titleLabel = wx.StaticText(panel, -1, _translate("Title:"))
        self.titleBox = wx.TextCtrl(panel, -1, size=(400, -1))

        internalNameLabel = wx.StaticText(panel, -1, _translate("Internal name:"))
        self.internalNameBox = wx.TextCtrl(panel, -1, size=(400, -1))

        descrLabel = wx.StaticText(panel, -1, _translate("Description:"))
        self.descrBox = wx.TextCtrl(panel, -1, size=(400, 200),
                                    style=wx.TE_MULTILINE | wx.SUNKEN_BORDER)

        urlLabel = wx.StaticText(panel, -1, _translate("Study URl:"))
        self.urlBox = wx.TextCtrl(panel, -1, value=f"https://run.pavlovia.org/{self.pavloviaId}/"+"?participant={{%PROLIFIC_PID%}}", size=(400, -1))

        codeLabel = wx.StaticText(panel, -1, _translate("Code:"))
        self.codeBox = wx.TextCtrl(panel, -1, value="2CC39346", size=(400, -1))


        participantsLabel = wx.StaticText(panel, -1, _translate("Num participants:"))
        self.participantsBox = wx.TextCtrl(panel, -1, value="500", size=(400, -1))
        self.participantsBox.Bind(wx.EVT_KEY_UP, self.onCostUpdate)

        durationLabel = wx.StaticText(panel, -1, _translate("Study duration:"))
        self.durationBox = wx.TextCtrl(panel, -1, value="1", size=(400, -1))

        rewardLabel = wx.StaticText(panel, -1, _translate("Amount:"))
        self.rewardBox = wx.TextCtrl(panel, -1, value="0.13", size=(400, -1))
        self.rewardBox.Bind(wx.EVT_KEY_UP, self.onCostUpdate)

        totalLabel = wx.StaticText(panel, -1, _translate("Total Cost:"))
        self.totalBox = wx.StaticText(panel, -1, "")
        self.onCostUpdate(None)

        # buttons
        if self.isNew:
            buttonMsg = _translate("Save as draft")
        else:
            buttonMsg = _translate("Update")
        updateBtn = wx.Button(panel, -1, buttonMsg)
        updateBtn.Bind(wx.EVT_BUTTON, self.submitChanges)
        cancelBtn = wx.Button(panel, -1, _translate("Cancel"))
        cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        if sys.platform == "win32":
            btns = [updateBtn, cancelBtn]
        else:
            btns = [cancelBtn, updateBtn]
        btnSizer.AddMany(btns)

        # do layout
        fieldsSizer = wx.FlexGridSizer(cols=2, rows=9, vgap=5, hgap=5)
        fieldsSizer.AddMany([(titleLabel, 0, wx.ALIGN_RIGHT), self.titleBox,
                             (internalNameLabel, 0, wx.ALIGN_RIGHT), self.internalNameBox,
                             (descrLabel, 0, wx.ALIGN_RIGHT), self.descrBox,
                             (urlLabel, 0, wx.ALIGN_RIGHT), self.urlBox,
                             (codeLabel, 0, wx.ALIGN_RIGHT), self.codeBox,
                             (participantsLabel, 0, wx.ALIGN_RIGHT), self.participantsBox,
                             (durationLabel, 0, wx.ALIGN_RIGHT), self.durationBox,
                             (rewardLabel, 0, wx.ALIGN_RIGHT), self.rewardBox,
                             (totalLabel, 0, wx.ALIGN_RIGHT), self.totalBox])

        border = wx.BoxSizer(wx.VERTICAL)
        border.Add(fieldsSizer, 0, wx.ALL, 5)
        border.Add(btnSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizerAndFit(border)
        self.Fit()

    def onCostUpdate(self, evt=None):
        participants = as_int(self.participantsBox.GetValue())
        reward = as_decimal(self.rewardBox.GetValue())

        session = prolific.getCurrentSession()
        total = session.calculate_total_price(participants, reward)
        self.totalBox.SetLabel(total)

    def onCancel(self, evt=None):
        self.EndModal(wx.ID_CANCEL)

    def submitChanges(self, evt=None):
        session = prolific.getCurrentSession()
        if not session.user:
            return
        # get current values
        title = self.titleBox.GetValue()
        internal_name = self.internalNameBox.GetValue()
        description = self.descrBox.GetValue()
        url = self.urlBox.GetValue()
        code = self.codeBox.GetValue()
        participants = as_int(self.participantsBox.GetValue())
        duration = as_int(self.durationBox.GetValue())
        reward = as_decimal(self.rewardBox.GetValue())

        # then create/update
        if self.isNew:
            project = session.createProject(pavloviaId=self.pavloviaId,
                                            title=title,
                                            internal_name=internal_name,
                                            description=description,
                                            url=url,
                                            code=code,
                                            participants=participants,
                                            duration=duration,
                                            reward=reward)
            self.project = project
            self.project._newRemote = True
        else:  # we're changing metadata of an existing project. Don't sync
            self.project.pavloviaId = self.pavloviaId
            self.project.prolific.name = title
            self.project.prolific.description = description
            self.project.prolific.description = description
            self.project._newRemote = False

        self.EndModal(wx.ID_OK)
        prolific.knownProjects.save()
        self.parent.prolific_project = self.project

    def onBrowseLocal(self, evt=None):
        newPath = setLocalPath(self, path=self.filename)
        if newPath:
            self.localBox.SetLabel(newPath)
            self.Layout()
            if self.project:
                self.project.localRoot = newPath
        self.Raise()


class DetailsPanel(scrlpanel.ScrolledPanel):

    def __init__(self, parent, noTitle=False,
                 style=wx.VSCROLL | wx.NO_BORDER,
                 project={}):

        scrlpanel.ScrolledPanel.__init__(self, parent, -1, style=style)
        self.parent = parent
        self.project = project  # type: prolific.ProlificProject
        self.noTitle = noTitle
        self.localFolder = ''
        self.syncPanel = None

        if not noTitle:
            self.title = wx.StaticText(parent=self, id=-1,
                                       label="", style=wx.ALIGN_CENTER)
            font = wx.Font(18, wx.DECORATIVE, wx.NORMAL, wx.BOLD)
            self.title.SetFont(font)

        # if we've synced before we should know the local location
        self.localFolderCtrl = wx.StaticText(
            parent=self, id=wx.ID_ANY,
            label=_translate("Local root: "))
        self.browseLocalBtn = wx.Button(parent=self, id=wx.ID_ANY,
                                        label=_translate("Browse..."))
        self.browseLocalBtn.Bind(wx.EVT_BUTTON, self.onBrowseLocalFolder)

        # remote attributes
        self.url = wxhl.HyperLinkCtrl(parent=self, id=-1,
                                      label="https://prolific.co",
                                      URL="https://prolific.co",
                                      )
        self.description = wx.StaticText(parent=self, id=-1,
                                         label=_translate(
                                             "Select a project for details"))
        self.tags = wx.StaticText(parent=self, id=-1,
                                  label="")
        self.visibility = wx.StaticText(parent=self, id=-1,
                                        label="")

        self.syncButton = wx.Button(self, -1, _translate("Sync..."))
        self.syncButton.Enable(False)
        self.syncButton.Bind(wx.EVT_BUTTON, self.onSyncButton)
        self.syncPanel = sync.SyncStatusPanel(parent=self, id=wx.ID_ANY)

        # layout
        # sizers: on the right we have detail
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        # self.sizer.Add(wx.StaticText(self, -1, _translate("Project Info")),
        #                flag=wx.ALL,
        #                border=5)
        if not noTitle:
            self.sizer.Add(self.title, border=5,
                           flag=wx.ALL | wx.CENTER)
        self.sizer.Add(self.url, border=5,
                       flag=wx.ALL | wx.CENTER)
        self.sizer.Add(self.localFolderCtrl, border=5,
                             flag=wx.ALL | wx.EXPAND),
        self.sizer.Add(self.browseLocalBtn, border=5,
                             flag=wx.ALL | wx.LEFT)
        self.sizer.Add(self.tags, border=5, flag=wx.ALL | wx.EXPAND)
        self.sizer.Add(self.visibility, border=5, flag=wx.ALL | wx.EXPAND)
        self.sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL),
                       flag=wx.ALL | wx.EXPAND)
        self.sizer.Add(self.description, border=10, flag=wx.ALL | wx.EXPAND)

        self.sizer.Add(wx.StaticLine(self, -1, style=wx.LI_HORIZONTAL),
                       flag=wx.ALL | wx.EXPAND)
        self.sizer.Add(self.syncButton,
                       flag=wx.ALL | wx.RIGHT, border=5)
        self.sizer.Add(self.syncPanel, border=5, proportion=1,
                       flag=wx.ALL | wx.RIGHT | wx.EXPAND)

        if self.project:
            self.setProject(self.prolific_project)
            self.syncPanel.setStatus(_translate("Ready to sync"))
        else:
            self.syncPanel.setStatus(
                    _translate("This file doesn't belong to a project yet"))

        self.SetAutoLayout(True)
        self.SetSizerAndFit(self.sizer)
        self.SetupScrolling()
        self.Bind(wx.EVT_SIZE, self.onResize)


    def setProject(self, project, localRoot=''):
        if not isinstance(project, prolific.ProlificProject):
            project = prolific.getCurrentSession().getProject(project)
        if project is None:
            return  # we're done
        self.project = project

        if not self.noTitle:
            # use the id (namespace/name) but give space around /
            self.title.SetLabel(project.id.replace("/", " / "))

        # url
        self.url.SetLabel(self.project.web_url)
        self.url.SetURL(self.project.web_url)

        # public / private
        if hasattr(project.attributes, 'description') and project.attributes['description']:
            self.description.SetLabel(project.attributes['description'])
        else:
            self.description.SetLabel('')
        if not hasattr(project, 'visibility'):
            visib = _translate("User not logged in!")
        elif project.visibility in ['public', 'internal']:
            visib = "Public"
        else:
            visib = "Private"
        self.visibility.SetLabel(_translate("Visibility: {}").format(visib))

        # do we have a local location?
        localFolder = project.localRoot
        if not localFolder:
            localFolder = _translate("<not yet synced>")
        self.localFolderCtrl.SetLabel(_translate("Local root: {}").format(localFolder))

        # Check permissions: login, fork or sync
        perms = project.permissions

        # we've got the permissions value so use it
        if not prolific.getCurrentSession().user.username:
            self.syncButton.SetLabel(_translate('Log in to sync...'))
        elif not perms or perms < prolific.permissions['developer']:
            self.syncButton.SetLabel(_translate('Fork + sync...'))
        else:
            self.syncButton.SetLabel(_translate('Sync...'))
        self.syncButton.Enable(True)  # now we have a project we should enable

        while None in project.tags:
            project.tags.remove(None)
        self.tags.SetLabel(_translate("Tags:") + " " + ", ".join(project.tags))
        # call onResize to get correct wrapping of description box and title
        self.onResize()

    def onResize(self, evt=None):
        if self.project is None:
            return
        w, h = self.GetSize()
        # if it hasn't been created yet then we won't have attributes
        if hasattr(self.project, 'attributes') and self.project.attributes['description'] is not None:
                self.description.SetLabel(self.project.attributes['description'])
                self.description.Wrap(w - 20)
        # noTitle in some uses of the detailsPanel
        if not self.noTitle and 'name' in self.project:
            self.title.SetLabel(self.project.name)
            self.title.Wrap(w - 20)
        self.Layout()

    def onSyncButton(self, event):
        if not prolific.haveGit:
            noGitWarning(parent=self.parent)
            return 0

        if self.project is None:
            raise AttributeError("User pressed the sync button with no "
                                 "current project existing.")

        # log in first if needed
        if not prolific.getCurrentSession().user.username:
            logInProlific(parent=self.parent)
            return

        # fork first if needed
        perms = self.project.permissions
        if not perms or perms < prolific.permissions['developer']:
            # specifying the group to fork to has no effect so don't use it
            # dlg = ForkDlg(parent=self.parent, project=self.project)
            # if dlg.ShowModal() == wx.ID_CANCEL:
            #     return
            # else:
            #     newGp = dlg.groupField.GetStringSelection()
            #     newName = dlg.nameField.GetValue()
            fork = self.project.forkTo()  # logged-in user
            self.setProject(fork.id)

        # if project.localRoot doesn't exist, or is empty
        if 'localRoot' not in self.project or not self.project.localRoot:
            # we first need to choose a location for the repository
            newPath = setLocalPath(self, self.project)
            if newPath:
                self.localFolderCtrl.SetLabel(
                    label=_translate("Local root: {}").format(newPath))
            self.project.local = newPath
            self.Layout()
            self.Raise()

        self.syncPanel.setStatus(_translate("Synchronizing..."))
        self.project.sync(infoStream=self.syncPanel.infoStream)
        self.parent.Raise()

    def onBrowseLocalFolder(self, evt):
        self.localFolder = setLocalPath(self, self.project)
        if self.localFolder:
            self.localFolderCtrl.SetLabel(
                label=_translate("Local root: {}").format(self.localFolder))
        self.localFolderCtrl.Wrap(self.GetSize().width)
        self.Layout()
        self.parent.Raise()


class ProjectFrame(wx.Dialog):

    def __init__(self, app, parent=None, style=None,
                 pos=wx.DefaultPosition, project=None):
        if style is None:
            style = (wx.DEFAULT_DIALOG_STYLE | wx.CENTER |
                     wx.TAB_TRAVERSAL | wx.RESIZE_BORDER)
        if project:
            title = project.title
        else:
            title = _translate("Project info")
        self.frameType = 'ProjectInfo'
        wx.Dialog.__init__(self, parent, -1, title=title, style=style,
                           size=(700, 500), pos=pos)
        self.app = app
        self.project = project
        self.parent = parent

        self.detailsPanel = DetailsPanel(parent=self, project=self.project)

        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer.Add(self.detailsPanel, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizerAndFit(self.mainSizer)

        if self.parent:
            self.CenterOnParent()
        self.Layout()

def syncProject(parent, project=None, closeFrameWhenDone=False):
    """A function to sync the current project (if there is one)

    Returns
    -----------
        1 for success
        0 for fail
        -1 for cancel at some point in the process
    """

    isCoder = hasattr(parent, 'currentDoc')

    # Test and reject sync from invalid folders
    if isCoder:
        currentPath = os.path.dirname(parent.currentDoc.filename)
    else:
        currentPath = os.path.dirname(parent.filename)

    currentPath = os.path.normcase(os.path.expanduser(currentPath))
    invalidFolders = [os.path.normcase(os.path.expanduser('~/Desktop')),
                      os.path.normcase(os.path.expanduser('~/My Documents'))]

    if currentPath in invalidFolders:
        wx.MessageBox(("You cannot sync projects from:\n\n"
                      "  - Desktop\n"
                      "  - My Documents\n\n"
                      "Please move your project files to another folder, and try again."),
                      "Project Sync Error",
                      wx.ICON_QUESTION | wx.OK)
        return -1

    if not project and "BuilderFrame" in repr(parent):
        # try getting one from the frame
        project = parent.prolific_project  # type: prolific.ProlificProject

    if not project:  # ask the user to create one

        # if we're going to create a project we need user to be logged in
        proSession = prolific.getCurrentSession()
        try:
            username = proSession.user.username
        except:
            username = logInProlific(parent)
        if not username:
            return -1  # never logged in

    if not project:  # we did our best for them. Give up!
        return 0



class ForkDlg(wx.Dialog):
    """Simple dialog to help choose the location/name of a forked project"""
    # this dialog is working fine, but the API call to fork to a specific
    # namespace doesn't appear to work
    def __init__(self, project, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        existingName = project.name
        session = prolific.getCurrentSession()
        groups = [session.user.username]
        msg = wx.StaticText(self, label="Where shall we fork to?")
        groupLbl = wx.StaticText(self, label="Group:")
        self.groupField = wx.Choice(self, choices=groups)
        nameLbl = wx.StaticText(self, label="Project name:")
        self.nameField = wx.TextCtrl(self, value=project.name)

        fieldsSizer = wx.FlexGridSizer(cols=2, rows=2, vgap=5, hgap=5)
        fieldsSizer.AddMany([groupLbl, self.groupField,
                             nameLbl, self.nameField])

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(wx.Button(self, id=wx.ID_OK, label="OK"))
        buttonSizer.Add(wx.Button(self, id=wx.ID_CANCEL, label="Cancel"))

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(msg, 1, wx.ALL, 5)
        mainSizer.Add(fieldsSizer, 1, wx.ALL, 5)
        mainSizer.Add(buttonSizer, 1, wx.ALL | wx.ALIGN_RIGHT, 5)

        self.SetSizerAndFit(mainSizer)
        self.Layout()


class ProjectRecreator(wx.Dialog):
    """Use this Dlg to handle the case of a missing (deleted?) remote project
    """

    def __init__(self, project, parent, *args, **kwargs):
        wx.Dialog.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.project = project
        existingName = project.name
        msgText = _translate("points to a remote that doesn't exist (deleted?).")
        msgText += (" "+_translate("What shall we do?"))
        msg = wx.StaticText(self, label="{} {}".format(existingName, msgText))
        choices = [_translate("(Re)create a project"),
                   "{} ({})".format(_translate("Point to an different location"),
                                    _translate("not yet supported")),
                   _translate("Forget the local git repository (deletes history keeps files)")]
        self.radioCtrl = wx.RadioBox(self, label='RadioBox', choices=choices,
                                     majorDimension=1)
        self.radioCtrl.EnableItem(1, False)
        self.radioCtrl.EnableItem(2, False)

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(wx.Button(self, id=wx.ID_OK, label=_translate("OK")),
                      1, wx.ALL, 5)
        buttonSizer.Add(wx.Button(self, id=wx.ID_CANCEL, label=_translate("Cancel")),
                      1, wx.ALL, 5)
        mainSizer.Add(msg, 1, wx.ALL, 5)
        mainSizer.Add(self.radioCtrl, 1, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        mainSizer.Add(buttonSizer, 1, wx.ALL | wx.ALIGN_RIGHT, 1)

        self.SetSizer(mainSizer)
        self.Layout()

    def ShowModal(self):
        if wx.Dialog.ShowModal(self) == wx.ID_OK:
            choice = self.radioCtrl.GetSelection()
            if choice == 0:
                editor = ProjectEditor(parent=self.parent,
                                       localRoot=self.project.localRoot)
                if editor.ShowModal() == wx.ID_OK:
                    self.project = editor.project
                    return 1  # success!
                else:
                    return -1  # user cancelled
            elif choice == 1:
                raise NotImplementedError("We don't yet support redirecting "
                                          "your project to a new location.")
            elif choice == 2:
                raise NotImplementedError("Deleting the local git repo is not "
                                          "yet implemented")
        else:
            return -1


def as_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def as_decimal(value):
    try:
        return Decimal(value)
    except Exception:
        return Decimal("0")
