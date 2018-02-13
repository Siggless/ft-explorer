#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (c) 2018, CJ Kucera
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

from . import data
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
            if len(node.data) > 0:
                self.display.setNode(node)
            else:
                self.display.setText('(no data)')
        else:
            self.display.setText('(nothing selected)')

class DataDisplay(QtWidgets.QTextEdit):
    """
    Display area for our data
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.node = None
        self.setText('(nothing selected)')
        self.setReadOnly(True)

        # Use a Monospaced font
        font = QtGui.QFont('Monospace')
        font.setStyleHint(font.Monospace)
        self.setFont(font)

        # Default to not word-wrapping
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)

    def setText(self, text, clear_node=True):
        """
        Sets text
        """
        if clear_node:
            self.node = None
        super().setText(text)

    def setHtml(self, text, clear_node=True):
        """
        Sets HTML
        """
        if clear_node:
            self.node = None
        super().setHtml(text)

    def setPlainText(self, text, clear_node=True):
        """
        Sets plain text
        """
        if clear_node:
            self.node = None
        super().setPlainText(text)

    def setNode(self, node):
        """
        Sets our currently-shown node, which will take into account our
        multiline option.
        """
        self.node = node
        self.updateText()

    def updateText(self):
        """
        Updates the text that we're showing, taking into account our
        multiline option.
        """
        # Only update if we have a node
        if self.node:

            do_multiline = self.parent.toolbar.action_multiline.isChecked()
            if do_multiline:
                # This is all pretty hacky, but seems to work fine.
                output = []
                for line in self.node.data:
                    indent_level = 1
                    parts = line.split('=', 1)
                    if len(parts) == 1:
                        output.append(line)
                    else:
                        chars = [char for char in parts[0]]
                        chars.append('=')
                        for char in parts[1]:
                            if char == '(':
                                indent_level += 1
                                chars.append(char)
                                chars.append("\n")
                                output.append(''.join(chars))
                                chars = [' '*(indent_level*4)]
                            elif char == ')':
                                if indent_level > 1:
                                    indent_level -= 1
                                chars.append("\n")
                                output.append(''.join(chars))
                                chars = [' '*(indent_level*4)]
                                chars.append(char)
                            elif char == ',' and indent_level > 1:
                                chars.append(char)
                                chars.append("\n")
                                output.append(''.join(chars))
                                chars = [' '*(indent_level*4)]
                            else:
                                chars.append(char)
                        output.append(''.join(chars))
            else:
                output = self.node.data

            # Display
            self.setText(''.join(output), clear_node=False)

class MainToolBar(QtWidgets.QToolBar):
    """
    Toolbar to hold a few toggles for us
    """

    def __init__(self, parent):

        super().__init__(parent)

        self.action_wrap = self.addAction('Word Wrap', parent.toggle_word_wrap)
        self.action_wrap.setCheckable(True)

        self.action_multiline = self.addAction('Multiline', parent.toggle_multiline)
        self.action_multiline.setCheckable(True)

class GUI(QtWidgets.QMainWindow):
    """
    Main application window
    """

    def __init__(self, data):
        super().__init__()

        # Store our data
        self.data = data

        # Set some window properties 
        self.setMinimumSize(500, 400)
        self.resize(500, 400)
        self.setWindowTitle('FT Explorer')

        # Load our toolbar
        self.toolbar = MainToolBar(self)
        self.addToolBar(self.toolbar)

        # Set up a QSplitter
        splitter = QtWidgets.QSplitter()

        # Set up our display area and add it to the hbox
        self.display = DataDisplay(self)

        # Set up our treeview
        self.treeview = MainTree(self, self.data, self.display)

        # Add both to the splitter
        splitter.addWidget(self.treeview)
        splitter.addWidget(self.display)

        # Set our stretch factors, for when the window is resized
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Use the splitter as our main widget
        self.setCentralWidget(splitter)

        # Here we go!
        self.show()

    def toggle_word_wrap(self):
        """
        Toggle word wrapping
        """
        do_wrap = self.toolbar.action_wrap.isChecked()
        if do_wrap:
            self.display.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        else:
            self.display.setWordWrapMode(QtGui.QTextOption.NoWrap)

    def toggle_multiline(self):
        """
        Toggle multiline output
        """
        self.display.updateText()

class Application(QtWidgets.QApplication):
    """
    Main application
    """

    def __init__(self):
        """
        Initialization
        """

        super().__init__([])
        self.data = data.Data()
        self.app = GUI(self.data)
