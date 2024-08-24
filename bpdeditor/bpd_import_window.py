import qdarkgraystyle
from PyQt5 import QtWidgets, QtGui, QtCore
from ftexplorer.data import Data, Node
from bpdeditor.bpd_gui import BPDWindow

class MainToolBar(QtWidgets.QToolBar):
    """
    Toolbar to hold a few toggles for us
    """

    def __init__(self, parent):

        super().__init__(parent)

        self.action_dark = self.addAction('Dark Theme', parent.toggle_dark)
        self.action_dark.setCheckable(True)
        self.action_dark.setChecked(parent.settings.value('toggles/darktheme', False, type=bool))

        self.action_wrap = self.addAction('Word Wrap', parent.toggle_word_wrap)
        self.action_wrap.setCheckable(True)
        self.action_wrap.setChecked(parent.settings.value('bpdimportwindow/toggles/wordwrap', False, type=bool))

        # self.action_multiline = self.addAction('Multiline', parent.toggle_multiline)
        # self.action_multiline.setCheckable(True)
        # self.action_multiline.setChecked(parent.settings.value('bpdimportwindow/toggles/multiline', True, type=bool))

        # self.action_syntax = self.addAction('Syntax Highlighting', parent.toggle_syntax)
        # self.action_syntax.setCheckable(True)
        # self.action_syntax.setChecked(parent.settings.value('bpdimportwindow/toggles/syntax', True, type=bool))
        
        self.action_load = self.addAction('Load', parent.load_bpd_text)
        self.action_load.setCheckable(True)
        self.action_load.setChecked(True)
        

class BPDImportWindow(QtWidgets.QMainWindow):
    """
    Window for the exported BPD text display
    """

    def __init__(self, settings, app, bpdWindow):
        super().__init__()
        
        # Store our data
        self.settings = settings
        self.app = app
        self.bpdWindow:BPDWindow = bpdWindow

        # Set some window properties 
        self.setMinimumSize(700, 500)
        self.resize(
            self.settings.value('bpdimportwindow/width', 700, type=int),
            self.settings.value('bpdimportwindow/height', 500, type=int)
            )
        self.setWindowTitle('BPD Editor Import')

        # Load our toolbar
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)

        # Set up Ctrl-Q to quit
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_Q), self)
        shortcut.activated.connect(self.action_quit)
        
        from ftexplorer.gui import DataDisplay  # Here to prevent circular import
        self.display = DataDisplay(self)
        self.display.setReadOnly(False)
        self.display.setText('BehaviorSequences(0)=(\n\tPASTE SEQUENCE DUMP AND CLICK LOAD BUTTON\n)')
        self.setCentralWidget(self.display)

        # Call out to a couple toggle functions, so that we're
        # applying our saved QSettings.  There's more elegant ways
        # to be doing this, but whatever.
        self.toggle_dark()

        # Here we go!
        self.show()

    def load_bpd_text(self):
        self.toolbar.action_load.setChecked(True)
        importNode = Node('BPD Import')
        importNode.loaded=True
        importNode.has_data=True
        importNode.data=['BPD Import','BehaviorProviderDefinition'] # Need the second line to pass is_valid_node
        cleanInputText = self.display.toPlainText().replace('\n','').replace('\t','').replace(' ','')
        importNode.data.append(cleanInputText)
        if not BPDWindow.is_valid_node(importNode):
            QtWidgets.QMessageBox.information(self, 'Error', 'I can\'t parse that text into a BPD!\nMake sure the top level is the BehaviorSequence list:\n\nBehaviorSequences(0)=(\nSEQUENCE DATA\n)')
            return
        
        self.bpdWindow.hide()
        self.bpdWindow.graphFrame.ClearCanvas()
        self.bpdWindow.set_node(importNode)
        self.bpdWindow.show()
        self.bpdWindow.graphFrame.OrganiseTree()
        self.close()

    def toggle_word_wrap(self):
        """
        Toggle word wrapping
        """
        do_wrap = self.toolbar.action_wrap.isChecked()
        self.settings.setValue('bpdimportwindow/toggles/wordwrap', do_wrap)
        if do_wrap:
            self.display.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        else:
            self.display.setWordWrapMode(QtGui.QTextOption.NoWrap)

    def toggle_multiline(self):
        """
        Toggle multiline output
        """
        self.settings.setValue('bpdimportwindow/toggles/multiline', self.toolbar.action_multiline.isChecked())
        self.display.updateText()

    def toggle_syntax(self):
        """
        Toggle syntax highlighting
        """
        self.settings.setValue('bpdimportwindow/toggles/syntax', self.toolbar.action_syntax.isChecked())
        self.display.updateText()

    def toggle_dark(self):
        """
        Toggles our dark theme
        """
        do_dark = self.toolbar.action_dark.isChecked()
        self.settings.setValue('toggles/darktheme', do_dark)
        if do_dark:
            self.app.setStyleSheet(qdarkgraystyle.load_stylesheet_pyqt5())
        else:
            self.app.setStyleSheet('')
        self.display.updateText()

    def action_quit(self):
        """
        Exit the window
        """
        self.close()

    def closeEvent(self, event):
        """
        Save our window state; used when the app is closing.
        """
        self.settings.setValue('bpdimportwindow/width', self.size().width())
        self.settings.setValue('bpdimportwindow/height', self.size().height())
        