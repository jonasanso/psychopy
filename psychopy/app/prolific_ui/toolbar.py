import wx

from os.path import join
from .. import icons, dialogs
from .project import syncProject, ProjectFrame
from .search import SearchFrame
from .user import UserEditor

from psychopy.localization import _translate


class ProlificButtons:

    def __init__(self, frame, toolbar, tbSize):
        self.frame = frame
        self.app = frame.app
        self.toolbar = toolbar
        self.tbSize = tbSize
        self.btnHandles = {}

    def addProlificTools(self, buttons=[]):

        info = {}
        info['prolificRun'] = {
            'emblem': 'run',
            'func': self.frame.onProlificRun,
            'label': _translate('Run online'),
            'tip': _translate('Run the study online (with prolific.co)')}
        info['prolificUser'] = {
            'emblem': 'user',
            'func': self.onProlificUser,
            'label': _translate('Log in to Prolific'),
            'tip': _translate('Log in to (or create user at) prolific.co')}
        info['prolificProject'] = {
            'emblem': 'info',
            'func': self.onProlificProject,
            'label': _translate('View project'),
            'tip': _translate('View details of this project')}

        if not buttons:  # allows panels to select subsets
            buttons = info.keys()

        for buttonName in buttons:
            emblem = info[buttonName]['emblem']
            btnFunc = info[buttonName]['func']
            label = info[buttonName]['label']
            tip = info[buttonName]['tip']
            self.btnHandles[buttonName] = self.app.iconCache.makeBitmapButton(
                    parent=self,
                    filename='prolific.png', label=label, name=buttonName,
                    emblem=emblem,
                    toolbar=self.toolbar, tip=tip, size=self.tbSize)
            self.toolbar.Bind(wx.EVT_TOOL, btnFunc, self.btnHandles[buttonName])

    def onProlificSync(self, evt=None):
        syncProject(parent=self.frame, project=self.frame.project)

    def onProlificRun(self, evt=None):
        if self.frame.project:
            self.frame.project.prolificStatus = 'ACTIVATED'
            url = "https://run.prolific.co/{}/html".format(
                    self.frame.project.id)
            wx.LaunchDefaultBrowser(url)

    def onProlificUser(self, evt=None):
        userDlg = UserEditor()
        if userDlg.user:
            userDlg.ShowModal()
        else:
            userDlg.Destroy()

    def onProlificSearch(self, evt=None):
        searchDlg = SearchFrame(
                app=self.frame.app, parent=self.frame,
                pos=self.frame.GetPosition())
        searchDlg.Show()

    def onProlificProject(self, evt=None):
        if self.frame.prolific_project:
            wx.LaunchDefaultBrowser(self.frame.prolific_project.url)
        else:
            infoDlg = dialogs.MessageDialog(parent=None, type='Info',
                                            message=_translate(
                                                    "You need to "
                                                    " to create a project first"))
            infoDlg.Show()

