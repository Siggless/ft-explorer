from __future__ import annotations
from typing import List
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from .bpd_classes import *
from .bpd_gui import *
from .model_outlink import *

"""
Output Link Views
Output Connections can use the Model because an output always has a connection
"""
class OutputLinksList(QFrame):
    """ The expandable widget list for each output link. """
    def __init__(self, parent:SequenceNode, modelIndexes:List[int]):
        super().__init__(parent)
        self.parentNode: SequenceNode = parent
        self.sequence: BehaviorSequence = self.parentNode.graph.sequence
        
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.hide()
        layout = QGridLayout(self)
        # Headers
        layout.addWidget(QLabel("Link ID"),0,0)
        layout.addWidget(QLabel("Activate Delay"),0,1)
        helpButton = QPushButton("?")
        helpButton.clicked.connect(self.Help)
        layout.addWidget(helpButton,0,2,Qt.AlignmentFlag.AlignTrailing)
        # New Button
        self.newButton = QPushButton("+")
        self.newButton.clicked.connect(self.NewRow)
        layout.addWidget(self.newButton,layout.rowCount()+1,0,1,2)
        self.items: List[OutputLinksListItem] = []
        for i in modelIndexes:
            self.AddRow(layout, i)
    
    def AddRow(self, layout:QGridLayout, modelIndex:int):
        newItem = OutputLinksListItem(self, modelIndex)
        self.items.append(newItem)
        
        i = layout.rowCount()-1
        layout.addWidget(newItem.idBox,i,0)
        layout.addWidget(newItem.delayBox,i,1)
        layout.addWidget(newItem.removeButton,i,2,2,1,Qt.AlignmentFlag.AlignTrailing)
        layout.addWidget(newItem.dropdown,i+1,0,1,2)
        layout.addWidget(self.newButton,i+2,0,1,2)
    
    def NewRow(self, linkToIndex: int = None):
        model = self.sequence.outLinkModel
        newIndex = model.rowCount()
        newItem = model.newItem()
        self.parentNode.modelItem.AddOutLink(newIndex)
        self.parentNode.outConnections.append(OutputLinkConnection(self.parentNode.graph, newItem, self.parentNode, -1))
        
        if linkToIndex:
            linkModel = self.sequence.outLinkModel
            linkModel.setData(linkModel.index(newIndex, 2), linkToIndex, Qt.EditRole)
        
        self.AddRow(self.layout(), newIndex)
        self.parentNode.adjustSize()
        self.parentNode.graph.canvas.update()

    def RemoveRow(self):
        for idx, row in enumerate(self.items):
            if row.removeButton is self.sender():
                model = self.sequence.outLinkModel
                model.removeRow(row.mapper.currentIndex())
                self.parentNode.modelItem.RemoveOutLink(row.mapper.currentIndex())
                
                self.items.remove(row)
                # NOTE this isn't actually removing the row from the grid layout but IDC
                self.layout().removeWidget(row.dropdown)
                self.layout().removeWidget(row.idBox)
                self.layout().removeWidget(row.delayBox)
                self.layout().removeWidget(row.removeButton)
                row.dropdown.deleteLater()      # Since still linked to other model?
                self.parentNode.adjustSize()
                self.parentNode.graph.canvas.update()
                return

    def Help(self):
        QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>What do?"\
            "<p>ActivateDelay is the time delay before this output fires."\
            "<p>LinkID is used on some behavior classes. This can be used to choose between output links - not firing them all."\
            "<br>Look in the behavior's UnrealScript class - they actually list the linkIDs with descriptions in the defaultproperties{} struct, and you can see where the ActivateBehaviorOutputLink() method is called in the code with a linkID."\
            "<br><br>Behavior_IntSwitchRange uses it to decide which output to fire."\
            "<br>Behavior_DamageSourceSwitch uses it to restrict damage types."\
            "<br>Behavior_TriggerDialogEvent uses it loop the behavior until the dialogue is finished... maybe?"\
            "<br>Some have a linkID of -1. ¯\\_(ツ)_/¯"\
            )

class OutputLinksListItem:
    """ A group of widgets representing a single OutputLinkData """
    def __init__(self, parent:OutputLinksList, modelIndex:int):
        self.sequence:BehaviorSequence = parent.sequence
        self.idBox:QLineEdit
        self.delayBox:QLineEdit
        self.removeButton:QPushButton
        self.dropdown:NodeCombo
        
        self.idBox = QLineEdit()
        self.delayBox = QLineEdit()
        self.removeButton = QPushButton("-")
        self.removeButton.clicked.connect(parent.RemoveRow)
        self.dropdown = NodeCombo()
        self.dropdown.SetHover(HoveringOver.OUT_LINK_COMBO, HoveringOver.GRAPH_NODE)
        self.dropdown.setModel(self.sequence.behaviorModel)
        
        model = self.sequence.outLinkModel
        self.mapper = QDataWidgetMapper(parent)
        self.mapper.setModel(model)
        self.mapper.addMapping(self.idBox, 0)
        self.mapper.addMapping(self.delayBox, 1)
        # When the dropdown changes we want to send the index, not the currentText
        self.mapper.addMapping(self.dropdown, 2, b"currentIndex")
        self.mapper.setCurrentIndex(modelIndex)

class OutputLinkConnection(QAbstractItemView, Connection):
    """ Output Connections can use the Model because an output always has a connection """
    def __init__(self, graph:GraphNode, modelItem:OutLinkItem, sourceNode:GraphNode, sourceIndex, destIndex=-1) -> None:
        self.modelItem = modelItem
        model = self.modelItem.model()
        linkedBehaviorIndex = self.modelItem.LinkIndex
        destNode = graph.FindNode(linkedBehaviorIndex)
        super().__init__(sourceNode=sourceNode, sourceIndex=sourceIndex, destNode=destNode, destIndex=destIndex)
        self.graph = graph
        self.setModel(model)
        self.setCurrentIndex(model.index(modelItem.row(), 2))
    
    def dataChanged(self, index, bottomRight, roles):
        myRow = self.currentIndex().row()
        if myRow < index.row() or myRow > bottomRight.row():
            return  # Not our item
        #If the linked index has changed we need to point this Connection to the new Behavior node
        newIndex: int = self.model().data(self.currentIndex(), Qt.EditRole)
        newDest = self.graph.FindNode(newIndex)
        self.ChangeDestination(newDest, -1)
        self.sourceNode.canvas.update()   # Trigger repaint
        
    def rowsAboutToBeRemoved(self, parent, start, end):
        row = self.currentIndex().row()
        if row >= start and row <= start:
            self.Remove()
