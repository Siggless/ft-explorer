#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (c) 2018-2021, CJ Kucera
# All rights reserved.
#   
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import qdarkgraystyle
from bpdeditor.bpd_gui import BPDWindow
from . import data, data_display
from PyQt5 import QtWidgets, QtGui, QtCore

class MainTree(QtWidgets.QTreeView):
    """
    Tree for all our objects
    """

    object_role = QtCore.Qt.UserRole + 1

    def __init__(self, parent, data, display):

        super().__init__(parent)
        self.parent = parent
        self.data = data
        self.display = display

        self.setMinimumWidth(200)
        self.setSelectionBehavior(self.SelectRows)
        self.setHeaderHidden(True)

        self.model = QtGui.QStandardItemModel()
        self.setModel(self.model)

        self.load_data(data)

    def load_data(self, data):
        """
        Loads the given dataset
        """

        self.model.clear()
        self.data = data
        for item in self.data:
            self.add_to_tree(item, self.model)

    def add_to_tree(self, item, parent):
        """
        Adds the specified item to the specified parent object,
        recursively.
        """
        item_obj = QtGui.QStandardItem(item.name)
        item_obj.setData(item, self.object_role)
        item_obj.setEditable(False)
        for next_item in item:
            self.add_to_tree(next_item, item_obj)
        parent.appendRow([item_obj])

    def selectionChanged(self, selected, deselected):
        """
        What to do when our selection changes.  Mostly just updating
        our label.
        """
        super().selectionChanged(selected, deselected)
        if len(selected.indexes()) > 0:
            node = selected.indexes()[0].data(self.object_role)
            if node.has_data:
                self.display.setNode(node)
            else:
                self.display.setText('(no data)')
            # Set BPD Editor button hightlight
            if self.parent.toolbar.action_bpd_editor:
                self.parent.toolbar.action_bpd_editor.setChecked(BPDWindow.is_valid_node(node))
        else:
            self.display.setText('(nothing selected)')

    def go_to_path(self, paths):
        """
        Given a list of paths, expand the whole tree and select the
        final element.
        """
        current = self.model.invisibleRootItem()
        found_path = False
        for path in paths:
            path_compare = path.name.lower()
            rowcount = current.rowCount()
            found_inner = False
            for rownum in range(rowcount):
                item = current.child(rownum)
                if item.text().lower() == path_compare:
                    current = item
                    self.setExpanded(current.index(), True)
                    found_path = True
                    found_inner = True
                    break
            if not found_inner:
                break

        # Select the item, if we found one.
        if found_path:
            self.setCurrentIndex(current.index())

class GameSelect(QtWidgets.QComboBox):
    """
    ComboBox to switch between BL2/TPS/AoDK data
    """

    def __init__(self, parent, maingui, data_bl2, data_tps, data_aodk):
        super().__init__(parent)
        self.maingui = maingui
        self.data_bl2 = data_bl2
        self.data_tps = data_tps
        self.data_aodk = data_aodk
        self.addItem('Borderlands 2', data_bl2)
        self.addItem('Pre-Sequel', data_tps)
        self.addItem('Dragon Keep (standalone)', data_aodk)
        current_game = self.maingui.settings.value('toggles/game', 'bl2')
        if current_game == 'bl2':
            self.setCurrentIndex(0)
        elif current_game == 'tps':
            self.setCurrentIndex(1)
        else:
            self.setCurrentIndex(2)
        self.currentIndexChanged.connect(self.index_changed)
        self.setSizeAdjustPolicy(self.AdjustToContents)

    def index_changed(self, index):
        """
        User selected a new game
        """
        if index == 0:
            self.maingui.settings.setValue('toggles/game', 'bl2')
        elif index == 1:
            self.maingui.settings.setValue('toggles/game', 'tps')
        elif index == 2:
            self.maingui.settings.setValue('toggles/game', 'aodk')
        self.maingui.switch_game(self.currentData())

class MainToolBar(QtWidgets.QToolBar):
    """
    Toolbar to hold a few toggles for us
    """

    def __init__(self, parent, data_bl2, data_tps, data_aodk):

        super().__init__(parent)

        self.action_dark = self.addAction('Dark Theme', parent.toggle_dark)
        self.action_dark.setCheckable(True)
        self.action_dark.setChecked(parent.settings.value('toggles/darktheme', False, type=bool))

        self.action_wrap = self.addAction('Word Wrap', parent.toggle_word_wrap)
        self.action_wrap.setCheckable(True)
        self.action_wrap.setChecked(parent.settings.value('toggles/wordwrap', False, type=bool))

        self.action_multiline = self.addAction('Multiline', parent.toggle_multiline)
        self.action_multiline.setCheckable(True)
        self.action_multiline.setChecked(parent.settings.value('toggles/multiline', True, type=bool))

        self.action_syntax = self.addAction('Syntax Highlighting', parent.toggle_syntax)
        self.action_syntax.setCheckable(True)
        self.action_syntax.setChecked(parent.settings.value('toggles/syntax', True, type=bool))

        self.action_bpd_editor = self.addAction('BPD Editor', parent.open_bpdeditor)
        self.action_bpd_editor.setCheckable(True)
        
        # Spacer, after which everything else will be right-aligned
        spacer_label = QtWidgets.QLabel()
        spacer_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.addWidget(spacer_label)

        # Game selection
        self.game_select = GameSelect(self, parent, data_bl2, data_tps, data_aodk)
        self.game_select.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        self.addWidget(self.game_select)

class GUI(QtWidgets.QMainWindow):
    """
    Main application window
    """

    def __init__(self, settings, data_bl2, data_tps, data_aodk, app):
        super().__init__()

        # Store our data
        self.settings = settings
        self.data_bl2 = data_bl2
        self.data_tps = data_tps
        self.data_aodk = data_aodk
        self.data = None
        self.bpd_windows=[]
        self.app = app

        # Set some window properties 
        self.setMinimumSize(700, 500)
        self.resize(
            self.settings.value('mainwindow/width', 700, type=int),
            self.settings.value('mainwindow/height', 500, type=int)
            )
        self.setWindowTitle('FT/BLCMM Explorer')

        # Set up Ctrl-Q to quit
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_Q), self)
        shortcut.activated.connect(self.action_quit)

        # Set up Ctrl-G to go to a specific object
        goto = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_G), self)
        goto.activated.connect(self.action_goto)

        # Set up Ctrl-F to find text inside the data display
        find = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_F), self)
        find.activated.connect(self.action_find)

        # Set up Enter to find the next result from a previous search
        find_next_enter = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Enter), self)
        find_next_return = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return), self)
        find_next_enter.activated.connect(self.action_find_next)
        find_next_return.activated.connect(self.action_find_next)

        # Load our toolbar
        self.toolbar = MainToolBar(self, data_bl2, data_tps, data_aodk)
        self.addToolBar(self.toolbar)

        # Set up a QSplitter
        self.splitter = QtWidgets.QSplitter()

        # Set up our display area and add it to the hbox
        self.display = data_display.DataDisplay(self)

        # Set up our treeview
        current_game = self.settings.value('toggles/game', 'bl2')
        if current_game == 'bl2':
            self.data = self.data_bl2
        elif current_game == 'tps':
            self.data = self.data_tps
        else:
            self.data = self.data_aodk
        self.treeview = MainTree(self, self.data, self.display)
        # Restore last opened node if set
        if self.settings.contains('mainwindow/lastobjectname'):
            try:
                paths = self.data.get_node_paths_by_full_object(self.settings.value('mainwindow/lastobjectname'))
                self.treeview.go_to_path(paths)
            except:
                print("no last object found!")

        # Add both to the splitter
        self.splitter.addWidget(self.treeview)
        self.splitter.addWidget(self.display)

        # Set our stretch factors, for when the window is resized
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # Use the splitter as our main widget
        self.setCentralWidget(self.splitter)

        # Call out to a couple toggle functions, so that we're
        # applying our saved QSettings.  There's more elegant ways
        # to be doing this, but whatever.
        self.toggle_word_wrap()
        self.toggle_dark()

        # Now that everything's set up, restore our splitter settings,
        # if we have any.
        splitter_settings = self.settings.value('mainwindow/splitter')
        if splitter_settings:
            self.splitter.restoreState(splitter_settings)

        # Here we go!
        self.show()

    def action_quit(self):
        """
        Exit the app
        """
        self.close()

    def closeEvent(self, event):
        """
        Save our window state; used when the app is closing.
        """
        self.settings.setValue('mainwindow/width', self.size().width())
        self.settings.setValue('mainwindow/height', self.size().height())
        self.settings.setValue('mainwindow/splitter', self.splitter.saveState())
        self.settings.setValue('mainwindow/datafont', self.display.currentFont().family())
        self.settings.setValue('mainwindow/datafontsize', self.display.currentFont().pointSizeF())

    def action_goto(self):
        """
        Go to a user-inputted object
        """
        (objectname, status) = QtWidgets.QInputDialog.getText(self,
                'Enter Object Name',
                'Go to object:',
                text='')
        if status:
            try:
                paths = self.data.get_node_paths_by_full_object(objectname)
                self.settings.setValue('mainwindow/lastobjectname', objectname)
                self.treeview.go_to_path(paths)
            except KeyError as e:
                QtWidgets.QMessageBox.information(self,
                    'Could Not Find Object',
                    'Object name <tt>{}</tt> was not found'.format(objectname))

        # Return focus to main window
        self.activateWindow()

    def action_find(self):
        """
        Find text inside our main data display
        """
        if self.display.search_str:
            initial_text = self.display.search_str
        else:
            initial_text = ''
        (searchstr, status) = QtWidgets.QInputDialog.getText(self,
                'Search for Text',
                'Text to search for:',
                text=initial_text)
        if status:
            self.display.search_for(searchstr)

        # Return focus to main window
        self.activateWindow()

    def action_find_next(self):
        """
        Advances to the next Find result
        """
        self.display.search_next()

    def toggle_word_wrap(self):
        """
        Toggle word wrapping
        """
        do_wrap = self.toolbar.action_wrap.isChecked()
        self.settings.setValue('toggles/wordwrap', do_wrap)
        if do_wrap:
            self.display.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        else:
            self.display.setWordWrapMode(QtGui.QTextOption.NoWrap)

    def toggle_multiline(self):
        """
        Toggle multiline output
        """
        self.settings.setValue('toggles/multiline', self.toolbar.action_multiline.isChecked())
        self.display.updateText()

    def toggle_syntax(self):
        """
        Toggle syntax highlighting
        """
        self.settings.setValue('toggles/syntax', self.toolbar.action_syntax.isChecked())
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

    def test_bpdeditor(self):
        """
        Tests opening the BPD Editor with every BPD in the data
        The data loop is copied from bpd_dot's generate_all_dots main method
        """
        game = self.data.game
        from .data import Data
        data = Data(game)

        objects = []
        #objects.extend(data.get_all_by_type('AIBehaviorProviderDefinition'))
        objects.extend(data.get_all_by_type('BehaviorProviderDefinition'))

        start_from=7000
        max_len_seen = 0
        for (idx, bpd_name) in enumerate(sorted(objects)[start_from:]):
            node = data.get_node_by_full_object(bpd_name)
            if not node:
                print('ERROR: {} not found'.format(game, bpd_name))
                
            if BPDWindow.is_valid_node(node):
                print(str(bpd_name))
                bpd_window = BPDWindow(self.settings, self.app)
                try:
                    bpd_window.set_node(node)
                    bpd_window.show()
                    bpd_window.graphFrame.OrganiseTree()
                    bpd_window.close()
                except Exception as e:
                    raise e
                
    def open_bpdeditor(self):
        """
        Opens a BPD Editor for the current object
        """
        #self.test_bpdeditor() # Test loading all BPDs
        if BPDWindow.is_valid_node(self.display.node):
            self.toolbar.action_bpd_editor.setChecked(True)
            bpd_window = BPDWindow(self.settings, self.app)
            self.bpd_windows.append(bpd_window) # Stop it being unloaded - but never gets disposed on close. IDK it works...
            try:
                bpd_window.set_node(self.display.node)
                bpd_window.show()
                bpd_window.graphFrame.OrganiseTree()
            except:
                QtWidgets.QMessageBox.information(self, 'Error', 'An error occured when setting up the nodes!')
        else:
            self.toolbar.action_bpd_editor.setChecked(False)
            QtWidgets.QMessageBox.information(self, 'Error', 'Current object is not a BPD!')

    def switch_game(self, data):
        """
        Switches to the game data contained in `data`.  Called
        from our GameSelect combo box
        """
        self.treeview.load_data(data)
        self.data = data
        self.display.initial_display()

class Application(QtWidgets.QApplication):
    """
    Main application
    """

    def __init__(self):
        """
        Initialization
        """

        super().__init__([])
        settings = QtCore.QSettings('Apocalyptech', 'FT Explorer')
        data_bl2 = data.Data('BL2')
        data_tps = data.Data('TPS')
        data_aodk = data.Data('AoDK')
        self.app = GUI(settings, data_bl2, data_tps, data_aodk, self)

