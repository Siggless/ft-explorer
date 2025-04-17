from __future__ import annotations
from typing import List
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from .bpd_classes import *
from .bpd_gui import *
from .model_varlink import *

"""
Variable Link Views
Variable Connections can't use the Model because a link doesn't always have a connection
"""
class VarLinksList(QFrame):
    """ The expandable widget list for each variable link. """
    def __init__(self, parent: SequenceNode, modelIndexes: List[int]):
        super().__init__(parent)
        self.parentNode = parent
        self.sequence: BehaviorSequence = self.parentNode.graph.sequence
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hide()
        layout = QGridLayout(self)
        # Headers
        layout.addWidget(QLabel("Property Name"),0,0)
        layout.addWidget(QLabel("Link Type"),0,1)
        layout.addWidget(QLabel("Connection Index"),0,2)
        helpButton = QPushButton("?")
        helpButton.clicked.connect(self.HelpVariables)
        layout.addWidget(helpButton,0,3,Qt.AlignmentFlag.AlignTrailing)
        # New Button
        self.newButton = QPushButton("+")
        self.newButton.clicked.connect(self.NewRow)
        layout.addWidget(self.newButton,layout.rowCount()+1,0,1,3)
        self.items: List[VarLinksListItem] = []
        for i in modelIndexes:
            self.AddRow(layout, i)
    
    def AddRow(self, layout: QGridLayout, modelIndex: int):
        newItem = VarLinksListItem(self, modelIndex)
        self.items.append(newItem)

        i = layout.rowCount()-1
        layout.addWidget(newItem.nameBox,i,0)
        layout.addWidget(newItem.dropdown,i,1)
        layout.addWidget(newItem.idBox,i,2)
        layout.addWidget(newItem.removeButton,i,3,2,1,Qt.AlignmentFlag.AlignTrailing)

        for varDropdown in newItem.varDropdownList:
            i = i + 1
            layout.addWidget(varDropdown,i,0,1,3)

        layout.addWidget(self.newButton,i+1,0,1,3)
    
    def NewRow(self, linkToIndex: int = None):
        model = self.sequence.varLinkModel
        newIndex = model.rowCount()
        
        cId = 0
        linkType = VariableLinkTypes.BVARLINK_Unknown.name
        from .bpd_nodes import EventNode
        if type(self.parentNode) is EventNode:
            linkType = VariableLinkTypes.BVARLINK_Output.name
            cId = len(self.items)
        
        newItem = model.newItem(cId, linkType)
        self.parentNode.modelItem.AddVarLink(newIndex)
                
        if linkToIndex:
            linkModel = self.sequence.varLinkModel
            linkModel.setData(linkModel.index(newIndex, 3), linkToIndex, Qt.EditRole)
        
        self.AddRow(self.layout(), newIndex)
        self.parentNode.MakeVarConnections()
        self.parentNode.adjustSize()
        self.parentNode.graph.canvas.update()
    
    def RemoveRow(self):
        for idx, row in enumerate(self.items):
            # If this wasn't sent from a button then just remove the first row
            if type(self.sender()) is not QPushButton or row.removeButton is self.sender():
                model = self.sequence.varLinkModel
                model.removeRow(row.mapper.currentIndex())
                self.parentNode.modelItem.RemoveVarLink(row.mapper.currentIndex())
                
                self.items.remove(row)

                # NOTE this isn't actually removing the row from the grid layout but IDC
                for dropDown in row.varDropdownList:
                    self.layout().removeWidget(dropDown)
                    dropDown.deleteLater()      # Since still linked to other model?
                self.layout().removeWidget(row.nameBox)
                self.layout().removeWidget(row.dropdown)
                self.layout().removeWidget(row.idBox)
                self.layout().removeWidget(row.removeButton)
                self.layout().removeWidget(row.removeButton)  # Remove twice cus spans two grid positions
                row.dropdown.deleteLater()      # Since still linked to other model?
                row.deleteLater()
                self.parentNode.MakeVarConnections()
                self.parentNode.adjustSize()
                self.parentNode.graph.canvas.update()
                return

    def HelpVariables(self):
        QMessageBox.information(self, 'Help', "Wiki Help: <a href='https://github.com/BLCM/BLCMods/wiki/BPD-classroom' style='color:orange'>BLCMods BPD Classroom</a>"\
            "<p>Variable Links are specific for each Event and Behavior type. They are defined in the game code. Not all available variables need to be linked, but those that are need to use the correct Link Type and info:"\
            "<br>For Events, it seems like only the Connection Indexes need to match."\
            "<br>For Behaviors, it seems like only the Property Names need to match."\
            "<br><p>Where do the Variable Links come from?"\
            "<p>Look inside WillowGame.upk, GearboxFramework.upk or Engine.upk,"\
            " using <a href='https://github.com/BLCM/BLCMods/wiki#modders-tools' style='color:orange'>UE Explorer</a>."\
            "<br>This editor also has json files containing all unique link properties found in the data, which will be suggested if any are found. But this is not an exhaustive list."\
            "<p>For Events, find the method with the name of the event in the parent class of the BPD."\
            " For example, ShieldDefinition has OnAmmoAbsorbed(), with variable links [Object ShieldOwner, Object DamageSource, Object DamageType]."\
            "<p>For Behaviors, see the class attributes in the UnrealScript for this behavior class. For variable ouputs, see the PublishBehaviorOutput() method."\
            )

class VarLinksListItem(QWidget):
    """
    A group of widgets representing a single VariableLinkData
    NOTE is a QWidget to prevent crashes on node deletion because of the signal link
    """
    def __init__(self, parent:VarLinksList, modelIndex:int):
        super().__init__(parent)
        self.parent: VarLinksList = parent
        self.link = parent.sequence.varLinkModel.item(modelIndex)
        link: VarLinkItem = self.link
        self.nameBox = QLineEdit(str(link.PropertyName))
        self.dropdown = NodeCombo()
        self.dropdown.SetHover(HoveringOver.UNKNOWN, HoveringOver.GRAPH_NODE)
        self.dropdown.setModel(link.sequence.linkTypeModel)
        self.idBox = QLineEdit(str(link.ConnectionIndex))
        self.removeButton = QPushButton("-")
        self.removeButton.clicked.connect(parent.RemoveRow)
        
        self.mapper = QDataWidgetMapper(parent)
        self.mapper.setModel(link.sequence.varLinkModel)
        self.mapper.addMapping(self.nameBox, 0)
        self.mapper.addMapping(self.dropdown, 1)
        self.mapper.addMapping(self.idBox, 2)
        
        # Add multiple combo-boxes populated with the vars list from that node
        self.varDropdownList = []
        linkedVarIndexes = link.GetAllVariableIndexes()
        if len(linkedVarIndexes) > 0:
            for idx, linkIndex in enumerate(linkedVarIndexes):
                varDropdown = NodeCombo()
                varDropdown.SetHover(HoveringOver.VAR_LINK_COMBO, HoveringOver.GRAPH_NODE)
                varDropdown.setModel(link.sequence.varModel)
                self.varDropdownList.append(varDropdown)
                self.mapper.addMapping(varDropdown, 3 + idx, bytearray("currentIndex", 'ascii'))
        else:
            # Still add a blank
            varDropdown = NodeCombo()
            varDropdown.SetHover(HoveringOver.VAR_LINK_COMBO, HoveringOver.GRAPH_NODE)
            varDropdown.setModel(link.sequence.varModel)
            self.varDropdownList.append(varDropdown)
            self.mapper.addMapping(varDropdown, 3, bytearray("currentIndex", 'ascii'))
            
        self.mapper.setCurrentIndex(modelIndex)
        self.mapper.model().dataChanged.connect(self.UpdateConnections)

    def UpdateConnections(self, index:QModelIndex, bottomRight:QModelIndex):
        if index.row() != self.mapper.currentIndex():
            return
        #if index.column() == 1 or index.column() >= 2:
            # Either the link type or the link index has changed.
            # Either way it's simpler to just recreate all the connections.
        self.parent.parentNode.MakeVarConnections()
        self.parent.parentNode.graph.canvas.update()

