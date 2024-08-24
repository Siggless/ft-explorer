import qdarkgraystyle
from PyQt5 import QtWidgets, QtGui, QtCore

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
        self.action_wrap.setChecked(parent.settings.value('bpdexportwindow/toggles/wordwrap', False, type=bool))

        self.action_multiline = self.addAction('Multiline', parent.toggle_multiline)
        self.action_multiline.setCheckable(True)
        self.action_multiline.setChecked(parent.settings.value('bpdexportwindow/toggles/multiline', True, type=bool))

        self.action_syntax = self.addAction('Syntax Highlighting', parent.toggle_syntax)
        self.action_syntax.setCheckable(True)
        self.action_syntax.setChecked(parent.settings.value('bpdexportwindow/toggles/syntax', True, type=bool))
        

class BPDExportWindow(QtWidgets.QMainWindow):
    """
    Window for the exported BPD text display
    """

    def __init__(self, settings, app, node):
        super().__init__()
        
        # Store our data
        self.settings = settings
        self.app = app

        # Set some window properties 
        self.setMinimumSize(700, 500)
        self.resize(
            self.settings.value('bpdexportwindow/width', 700, type=int),
            self.settings.value('bpdexportwindow/height', 500, type=int)
            )
        self.setWindowTitle('BPD Editor Export')

        # Load our toolbar
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)

        # Set up Ctrl-Q to quit
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_Q), self)
        shortcut.activated.connect(self.action_quit)
        
        from ftexplorer.gui import DataDisplay  # Here to prevent circular import
        self.display = DataDisplay(self)
        self.display.setNode(node)
        self.setCentralWidget(self.display)

        # Call out to a couple toggle functions, so that we're
        # applying our saved QSettings.  There's more elegant ways
        # to be doing this, but whatever.
        self.toggle_dark()

        # Here we go!
        self.show()

    def toggle_word_wrap(self):
        """
        Toggle word wrapping
        """
        do_wrap = self.toolbar.action_wrap.isChecked()
        self.settings.setValue('bpdexportwindow/toggles/wordwrap', do_wrap)
        if do_wrap:
            self.display.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        else:
            self.display.setWordWrapMode(QtGui.QTextOption.NoWrap)

    def toggle_multiline(self):
        """
        Toggle multiline output
        """
        self.settings.setValue('bpdexportwindow/toggles/multiline', self.toolbar.action_multiline.isChecked())
        self.display.updateText()

    def toggle_syntax(self):
        """
        Toggle syntax highlighting
        """
        self.settings.setValue('bpdexportwindow/toggles/syntax', self.toolbar.action_syntax.isChecked())
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
        self.settings.setValue('bpdexportwindow/width', self.size().width())
        self.settings.setValue('bpdexportwindow/height', self.size().height())
        